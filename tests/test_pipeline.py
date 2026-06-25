from pathlib import Path
import logging

from app.grammar import ShotGrammarAnalyzer
from app.models import Keyframes, Shot, VideoInfo
from app.pipeline import AnalysisPipeline


class FakeInfoService:
    def probe(self, video_path: Path) -> VideoInfo:
        assert video_path.name == "source.mp4"
        return VideoInfo(
            duration=6.0,
            fps=24.0,
            width=1080,
            height=1920,
            aspect_ratio="9:16",
            has_audio=True,
        )


class FakeShotService:
    def detect(self, video_path: Path, duration: float) -> list[Shot]:
        assert duration == 6.0
        return [
            Shot("S01", 0.0, 3.0, 3.0),
            Shot("S02", 3.0, 6.0, 3.0),
        ]


class FakeKeyframeService:
    def extract(self, video_path: Path, shots_dir: Path, shot: Shot) -> Keyframes:
        shot_dir = shots_dir / shot.shot_id
        shot_dir.mkdir(parents=True, exist_ok=True)
        for name in ["frame_start.jpg", "frame_mid.jpg", "frame_end.jpg"]:
            (shot_dir / name).write_bytes(b"jpg")
        return Keyframes(
            shot_id=shot.shot_id,
            frame_start=shot_dir / "frame_start.jpg",
            frame_mid=shot_dir / "frame_mid.jpg",
            frame_end=shot_dir / "frame_end.jpg",
            timestamps={"start": shot.start_time, "middle": 1.5, "end": 2.96},
        )


class FakeShotRefiner:
    def refine(
        self,
        video_path: Path,
        shots_dir: Path,
        candidate_shots: list[Shot],
    ) -> list[Shot]:
        assert [shot.shot_id for shot in candidate_shots] == ["S01", "S02"]
        return [Shot("S01", 0.0, 6.0, 6.0)]


class PassthroughShotRefiner:
    def refine(
        self,
        video_path: Path,
        shots_dir: Path,
        candidate_shots: list[Shot],
    ) -> list[Shot]:
        return candidate_shots


class FakeContextTrackService:
    def extract(self, video_path: Path, shots: list[Shot]) -> dict[str, object]:
        assert video_path.name == "source.mp4"
        assert [shot.shot_id for shot in shots] == ["S01", "S02"]
        return {
            "speech": {"enabled": False, "provider": None, "segments": []},
            "ocr": {"enabled": False, "provider": None, "segments": []},
        }


class FakeSceneStructureService:
    def group(self, shots: list[Shot]) -> list[dict[str, object]]:
        assert [shot.shot_id for shot in shots] == ["S01", "S02"]
        return [
            {
                "scene_id": "SC01",
                "start_time": 0.0,
                "end_time": 6.0,
                "duration": 6.0,
                "shot_ids": ["S01", "S02"],
                "summary": "test scene",
            }
        ]


def test_pipeline_analyzes_video_into_complete_result(tmp_path):
    workspace = tmp_path / "videos" / "abc123"
    source = workspace / "source.mp4"
    shots_dir = workspace / "shots"
    shots_dir.mkdir(parents=True)
    source.write_bytes(b"fake mp4")
    pipeline = AnalysisPipeline(
        info_service=FakeInfoService(),
        shot_service=FakeShotService(),
        shot_refiner=PassthroughShotRefiner(),
        keyframe_service=FakeKeyframeService(),
        context_track_service=FakeContextTrackService(),
        scene_structure_service=FakeSceneStructureService(),
        grammar_analyzer=ShotGrammarAnalyzer(),
    )

    result = pipeline.analyze(source, shots_dir)

    assert result["video_info"]["duration"] == 6.0
    assert [shot["shot_id"] for shot in result["shots"]] == ["S01", "S02"]
    assert len(result["keyframes"]) == 2
    assert result["context_tracks"]["speech"]["segments"] == []
    assert result["context_tracks"]["ocr"]["segments"] == []
    assert result["scenes"][0]["shot_ids"] == ["S01", "S02"]
    assert len(result["shot_grammar"]) == 2
    assert result["video_structure"]["video_structure"]["total_shots"] == 2


def test_pipeline_analyzes_refined_shots_after_candidate_detection(tmp_path):
    workspace = tmp_path / "videos" / "abc123"
    source = workspace / "source.mp4"
    shots_dir = workspace / "shots"
    shots_dir.mkdir(parents=True)
    source.write_bytes(b"fake mp4")
    pipeline = AnalysisPipeline(
        info_service=FakeInfoService(),
        shot_service=FakeShotService(),
        shot_refiner=FakeShotRefiner(),
        keyframe_service=FakeKeyframeService(),
        grammar_analyzer=ShotGrammarAnalyzer(),
    )

    result = pipeline.analyze(source, shots_dir)

    assert [item["shot_id"] for item in result["candidate_shots"]] == ["S01", "S02"]
    assert result["shots"] == [
        {"shot_id": "S01", "start_time": 0.0, "end_time": 6.0, "duration": 6.0}
    ]
    assert [item["shot_id"] for item in result["keyframes"]] == ["S01"]
    assert [item["shot_id"] for item in result["shot_grammar"]] == ["S01"]


def test_pipeline_reports_analysis_progress_events(tmp_path):
    workspace = tmp_path / "videos" / "abc123"
    source = workspace / "source.mp4"
    shots_dir = workspace / "shots"
    shots_dir.mkdir(parents=True)
    source.write_bytes(b"fake mp4")
    events = []
    pipeline = AnalysisPipeline(
        info_service=FakeInfoService(),
        shot_service=FakeShotService(),
        shot_refiner=PassthroughShotRefiner(),
        keyframe_service=FakeKeyframeService(),
        grammar_analyzer=ShotGrammarAnalyzer(),
    )

    pipeline.analyze(source, shots_dir, progress_callback=events.append)

    assert events[0]["stage"] == "video_info"
    assert any(event["stage"] == "keyframes" for event in events)
    assert any(event["stage"] == "vlm" for event in events)
    assert events[-1]["stage"] == "completed"
    assert events[-1]["progress"] == 100


def test_pipeline_reports_each_completed_shot_grammar_for_partial_persistence(tmp_path):
    workspace = tmp_path / "videos" / "abc123"
    source = workspace / "source.mp4"
    shots_dir = workspace / "shots"
    shots_dir.mkdir(parents=True)
    source.write_bytes(b"fake mp4")
    partials = []
    pipeline = AnalysisPipeline(
        info_service=FakeInfoService(),
        shot_service=FakeShotService(),
        shot_refiner=PassthroughShotRefiner(),
        keyframe_service=FakeKeyframeService(),
        grammar_analyzer=ShotGrammarAnalyzer(),
    )

    pipeline.analyze(source, shots_dir, partial_callback=partials.append)

    assert [partial["shot"]["shot_id"] for partial in partials] == ["S01", "S02"]
    assert partials[0]["grammar"]["shot_id"] == "S01"
    assert len(partials[-1]["shot_grammar"]) == 2


def test_pipeline_logs_analysis_progress_events(tmp_path, caplog):
    workspace = tmp_path / "videos" / "abc123"
    source = workspace / "source.mp4"
    shots_dir = workspace / "shots"
    shots_dir.mkdir(parents=True)
    source.write_bytes(b"fake mp4")
    pipeline = AnalysisPipeline(
        info_service=FakeInfoService(),
        shot_service=FakeShotService(),
        shot_refiner=PassthroughShotRefiner(),
        keyframe_service=FakeKeyframeService(),
        grammar_analyzer=ShotGrammarAnalyzer(),
    )

    with caplog.at_level(logging.INFO, logger="video_prompt"):
        pipeline.analyze(source, shots_dir)

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "stage=video_info" in messages
    assert "stage=keyframes" in messages
    assert "stage=vlm" in messages
    assert "stage=completed" in messages
