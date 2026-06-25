from pathlib import Path
import json
import sys
import types

import pytest

from app.grammar import ShotGrammarAnalyzer, VideoStructureSummarizer
from app.keyframes import KeyframeService
from app.models import NewContentInput, Shot, ShotGrammar
from app.prompt_compiler import PromptCompiler
from app.shot_detection import ShotDetectionService
from app.storage import VideoStorage


def test_storage_creates_expected_video_workspace(tmp_path):
    storage = VideoStorage(tmp_path)

    workspace = storage.create_workspace("sample.mp4")

    assert workspace.video_id
    assert workspace.video_dir == tmp_path / "videos" / workspace.video_id
    assert workspace.source_path == workspace.video_dir / "source.mp4"
    assert workspace.shots_dir == workspace.video_dir / "shots"
    assert workspace.shots_dir.exists()


def test_shot_detection_falls_back_to_fixed_three_second_segments():
    service = ShotDetectionService(scene_threshold=0.35, fallback_seconds=3.0)

    shots = service.fallback_segments(duration=7.2)

    assert shots == [
        Shot(shot_id="S01", start_time=0.0, end_time=3.0, duration=3.0),
        Shot(shot_id="S02", start_time=3.0, end_time=6.0, duration=3.0),
        Shot(shot_id="S03", start_time=6.0, end_time=7.2, duration=1.2),
    ]


def test_shot_detection_prefers_pyscenedetect_when_available(monkeypatch):
    class FakeTimecode:
        def __init__(self, seconds):
            self.seconds = seconds

        def get_seconds(self):
            return self.seconds

    def fake_detect(video_path, detector):
        assert video_path == "source.mp4"
        assert detector.threshold == 27.0
        return [
            (FakeTimecode(0.0), FakeTimecode(1.25)),
            (FakeTimecode(1.25), FakeTimecode(3.5)),
            (FakeTimecode(3.5), FakeTimecode(5.0)),
        ]

    class FakeContentDetector:
        def __init__(self, threshold):
            self.threshold = threshold

    fake_module = types.SimpleNamespace(
        detect=fake_detect,
        ContentDetector=FakeContentDetector,
    )
    monkeypatch.setitem(sys.modules, "scenedetect", fake_module)
    service = ShotDetectionService(use_pyscenedetect=True, pyscene_threshold=27.0)

    shots = service.detect(Path("source.mp4"), duration=5.0)

    assert shots == [
        Shot("S01", 0.0, 1.25, 1.25),
        Shot("S02", 1.25, 3.5, 2.25),
        Shot("S03", 3.5, 5.0, 1.5),
    ]


def test_shot_detection_falls_back_to_ffmpeg_when_pyscenedetect_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "scenedetect", None)
    service = ShotDetectionService(use_pyscenedetect=True)
    monkeypatch.setattr(service, "_detect_cut_times", lambda video_path: [2.0, 4.0])

    shots = service.detect(Path("source.mp4"), duration=6.0)

    assert shots == [
        Shot("S01", 0.0, 2.0, 2.0),
        Shot("S02", 2.0, 4.0, 2.0),
        Shot("S03", 4.0, 6.0, 2.0),
    ]


def test_shot_detection_command_does_not_require_null_video_encoder():
    service = ShotDetectionService(ffmpeg_path="ffmpeg", scene_threshold=0.2)

    command = service.build_detection_command(Path("source.mp4"))

    assert "-f" in command
    assert "image2pipe" in command
    assert "-c:v" in command
    assert "png" in command
    assert "null" not in command
    assert "'gt(scene" not in " ".join(command)
    assert any("showinfo" in item for item in command)


def test_shot_detection_raises_when_ffmpeg_detection_fails(monkeypatch):
    class Completed:
        returncode = 1
        stdout = ""
        stderr = "Encoder not found"

    monkeypatch.setattr("app.shot_detection.subprocess.run", lambda *a, **k: Completed())
    service = ShotDetectionService(ffmpeg_path="ffmpeg")

    with pytest.raises(RuntimeError, match="Encoder not found"):
        service._detect_cut_times(Path("source.mp4"))


def test_shot_detection_uses_opencv_when_ffmpeg_detection_fails(monkeypatch):
    service = ShotDetectionService(ffmpeg_path="ffmpeg", fallback_seconds=3.0)

    monkeypatch.setattr(
        service,
        "_detect_cut_times",
        lambda video_path: (_ for _ in ()).throw(RuntimeError("ffmpeg failed")),
    )
    monkeypatch.setattr(
        service,
        "_detect_cut_times_opencv",
        lambda video_path, duration: [2.4, 7.1],
    )

    shots = service.detect(Path("source.mp4"), duration=10.0)

    assert shots == [
        Shot(shot_id="S01", start_time=0.0, end_time=2.4, duration=2.4),
        Shot(shot_id="S02", start_time=2.4, end_time=7.1, duration=4.7),
        Shot(shot_id="S03", start_time=7.1, end_time=10.0, duration=2.9),
    ]


def test_opencv_cut_detection_respects_threshold_and_min_gap():
    service = ShotDetectionService(opencv_threshold=65.0, opencv_min_gap_seconds=3.0)

    cuts = service._cut_times_from_frame_scores(
        [
            (0.5, 20.0),
            (1.0, 80.0),
            (2.0, 90.0),
            (4.1, 70.0),
            (6.0, 64.0),
        ]
    )

    assert cuts == [1.0, 4.1]


def test_keyframe_service_plans_three_named_frames_per_shot(tmp_path):
    service = KeyframeService(ffmpeg_path="ffmpeg")
    shot = Shot(shot_id="S01", start_time=2.0, end_time=5.0, duration=3.0)

    planned = service.plan_keyframes(tmp_path, shot)

    assert planned.shot_id == "S01"
    assert planned.frame_start == tmp_path / "S01" / "frame_start.jpg"
    assert planned.frame_mid == tmp_path / "S01" / "frame_mid.jpg"
    assert planned.frame_end == tmp_path / "S01" / "frame_end.jpg"
    assert planned.timestamps == {"start": 2.0, "middle": 3.5, "end": 4.96}


def test_keyframe_service_writes_shot_meta_json(tmp_path, monkeypatch):
    service = KeyframeService(ffmpeg_path="ffmpeg")
    shot = Shot(shot_id="S01", start_time=2.0, end_time=5.0, duration=3.0)
    monkeypatch.setattr(service, "_extract_one", lambda video_path, timestamp, output_path: output_path.write_bytes(b"jpg"))

    keyframes = service.extract(Path("source.mp4"), tmp_path, shot)

    meta = json.loads((tmp_path / "S01" / "meta.json").read_text(encoding="utf-8"))
    assert meta == {
        "shot_id": "S01",
        "start_time": 2.0,
        "end_time": 5.0,
        "duration": 3.0,
        "frames": {
            "start": "frame_start.jpg",
            "middle": "frame_mid.jpg",
            "end": "frame_end.jpg",
        },
        "timestamps": keyframes.timestamps,
    }


def test_keyframe_ffmpeg_command_uses_jpeg_compatible_pixel_format(tmp_path):
    service = KeyframeService(ffmpeg_path="ffmpeg")

    command = service.build_extract_command(
        video_path=tmp_path / "source.mp4",
        timestamp=1.25,
        output_path=tmp_path / "frame_start.jpg",
    )

    assert "-pix_fmt" in command
    assert "yuvj420p" in command


def test_local_grammar_analyzer_outputs_stable_replaceable_json(tmp_path):
    analyzer = ShotGrammarAnalyzer()
    shot = Shot(shot_id="S01", start_time=0.0, end_time=2.4, duration=2.4)
    frames = KeyframeService("ffmpeg").plan_keyframes(tmp_path, shot)

    grammar = analyzer.analyze(shot, frames)

    payload = grammar.to_dict()
    assert payload["shot_id"] == "S01"
    assert payload["time_range"]["duration"] == 2.4
    assert set(payload["camera"]) == {
        "shot_size_start",
        "shot_size_end",
        "angle",
        "movement",
        "camera_energy",
    }
    assert "any " in payload["replaceable_variables"]["character_a"]
    assert "prompt_pattern" in payload


def test_summarizer_reports_global_video_structure(tmp_path):
    analyzer = ShotGrammarAnalyzer()
    frames = KeyframeService("ffmpeg").plan_keyframes(
        tmp_path, Shot("S01", 0.0, 3.0, 3.0)
    )
    grammar = analyzer.analyze(Shot("S01", 0.0, 3.0, 3.0), frames)

    summary = VideoStructureSummarizer().summarize([grammar])

    assert summary["video_structure"]["total_shots"] == 1
    assert summary["video_structure"]["average_shot_duration"] == 3.0
    assert summary["video_structure"]["dominant_shot_types"]


def test_prompt_compiler_generates_seedance_replicate_prompts_from_grammar():
    grammar = ShotGrammar(
        shot_id="S01",
        time_range={"start": 0.0, "end": 3.0, "duration": 3.0},
        shot_type="Extreme Long Shot / Low Angle",
        camera={
            "shot_size_start": "extreme wide shot",
            "shot_size_end": "extreme wide shot",
            "angle": "Low Angle",
            "movement": "Static / Slight Push In",
            "camera_energy": "slow and tense",
            "focal_length": "Wide Angle",
        },
        composition={
            "foreground": "Massive textured legs of a giant entity dominating left frame",
            "midground": "Tiny solitary figure standing on a ridge",
            "background": "Vast misty mountainous landscape with stormy sky",
            "scale_contrast": "Extreme size difference",
            "main_subject_position": "right third in distance",
            "secondary_subject_position": "left foreground",
            "spatial_relationship": "overwhelming threat versus isolated figure",
            "depth_structure": "giant foreground object leads, distant figure adds tension",
        },
        action_pattern={
            "start": "Static confrontation stance",
            "middle": "Environmental wind and mist move slowly",
            "end": "Threat remains unresolved",
            "dynamic_element": "Weapon tip visible in upper right corner",
        },
        emotion_pattern={
            "start": "oppressive calm",
            "middle": "tension increases",
            "end": "unresolved pressure",
            "tone": "Oppressive, Tense, Epic",
            "atmosphere": "Foreboding, Mythic",
        },
        editing_function="Establishing Shot / Spatial Orientation",
        continuity_rule="Maintain line of action between opposing forces",
        replaceable_variables={
            "foreground_object": "Giant legs / Monster feet / Ruined structure",
            "background_subject": "Small warrior / Lone traveler / Child",
        },
        prompt_pattern=(
            "Extreme low angle shot, massive foreground object dominating left frame, "
            "tiny background subject standing alone in distance on mountain ridge."
        ),
    )

    result = PromptCompiler().compile_replicate([grammar], aspect_ratio="16:9")

    item = result["generated_prompts"][0]
    prompt = item["prompt"]
    assert result["mode"] == "replicate"
    assert result["video_model"] == "Seedance 2.0"
    assert item["duration"] == "3s"
    assert item["seedance_prompt"] == prompt
    assert "Seedance 2.0" in prompt
    assert "16:9" in prompt
    assert "Massive textured legs" in prompt
    assert "Tiny solitary figure" in prompt
    assert "Low Angle" in prompt
    assert "Static / Slight Push In" in prompt
    assert "不要改变镜头景别" in item["negative_prompt"]


def test_prompt_compiler_generates_seedance_replicate_prompts_with_llm():
    class FakeLLMClient:
        def __init__(self):
            self.messages = []

        def analyze(self, messages):
            self.messages = messages
            return {
                "seedance_prompt": "Seedance 2.0 复刻：低机位拍摄巨大前景腿部和远处小人。",
                "negative_prompt": "不要改变低机位和尺度反差。",
                "source_reasoning": "重点保留低机位、巨大前景、远处小人和压迫感。",
            }

    grammar = ShotGrammar(
        shot_id="S01",
        time_range={"start": 0.0, "end": 3.0, "duration": 3.0},
        shot_type="Extreme Long Shot / Low Angle",
        camera={"angle": "Low Angle", "movement": "Static / Slight Push In"},
        composition={
            "foreground": "Massive textured legs",
            "background": "Tiny figure on mountain ridge",
        },
        action_pattern={"start": "Static confrontation stance"},
        emotion_pattern={"atmosphere": "Oppressive and epic"},
        editing_function="Establish scale",
        continuity_rule="Maintain spatial orientation",
        replaceable_variables={},
        prompt_pattern="Extreme low angle shot with massive foreground object.",
    )
    client = FakeLLMClient()

    result = PromptCompiler().compile_replicate_with_llm(
        [grammar],
        client=client,
        aspect_ratio="16:9",
    )

    item = result["generated_prompts"][0]
    prompt_payload = str(client.messages)
    assert result["mode"] == "replicate_llm"
    assert item["prompt"] == "Seedance 2.0 复刻：低机位拍摄巨大前景腿部和远处小人。"
    assert item["negative_prompt"] == "不要改变低机位和尺度反差。"
    assert item["source_reasoning"] == "重点保留低机位、巨大前景、远处小人和压迫感。"
    assert "Massive textured legs" in prompt_payload
    assert "只做原视频复刻" in prompt_payload


def test_prompt_compiler_runs_replicate_llm_requests_in_parallel():
    import threading
    import time

    class SlowLLMClient:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def analyze(self, messages):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1
            shot_id = messages[1]["content"].split('"shot_id": "')[1].split('"')[0]
            return {
                "seedance_prompt": f"prompt for {shot_id}",
                "negative_prompt": f"negative for {shot_id}",
                "source_reasoning": f"reason for {shot_id}",
            }

    def grammar(shot_id: str) -> ShotGrammar:
        return ShotGrammar(
            shot_id=shot_id,
            time_range={"start": 0.0, "end": 3.0, "duration": 3.0},
            shot_type="Extreme Wide Shot",
            camera={"angle": "Low Angle"},
            composition={"foreground": "Massive object"},
            action_pattern={"start": "Static"},
            emotion_pattern={"atmosphere": "Epic"},
            editing_function="Establish scale",
            continuity_rule="Maintain spatial orientation",
            replaceable_variables={},
            prompt_pattern="Low angle massive foreground object.",
        )

    client = SlowLLMClient()

    result = PromptCompiler().compile_replicate_with_llm(
        [grammar("S01"), grammar("S02"), grammar("S03")],
        client=client,
        max_workers=3,
    )

    assert client.max_active > 1
    assert [item["shot_id"] for item in result["generated_prompts"]] == [
        "S01",
        "S02",
        "S03",
    ]
    assert result["generated_prompts"][1]["prompt"] == "prompt for S02"


def test_prompt_compiler_injects_new_content_without_losing_shot_structure(tmp_path):
    shot = Shot("S01", 0.0, 3.0, 3.0)
    frames = KeyframeService("ffmpeg").plan_keyframes(tmp_path, shot)
    grammar = ShotGrammarAnalyzer().analyze(shot, frames)
    new_content = NewContentInput(
        target_style="AI 漫剧，半写实 3D，短剧感",
        new_story="女赏金猎人在雨夜质问机械改造男性为什么背叛她",
        character_a="年轻女赏金猎人，黑色短发，皮衣",
        character_b="机械改造男性，高大沉默，半张脸是金属结构",
        location="赛博朋克雨夜巷道，霓虹灯，积水地面",
        aspect_ratio="9:16",
        video_model="Seedance",
    )

    result = PromptCompiler().compile([grammar], new_content)

    prompt = result["generated_prompts"][0]["prompt"]
    assert result["global_style_prompt"] == "AI 漫剧，半写实 3D，短剧感"
    assert "年轻女赏金猎人" in prompt
    assert "机械改造男性" in prompt
    assert "赛博朋克雨夜巷道" in prompt
    assert "镜头结构" in prompt
    assert result["generated_prompts"][0]["negative_prompt"]
