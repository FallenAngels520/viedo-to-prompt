from fastapi.testclient import TestClient

from app.server import app


client = TestClient(app)


def test_health_route_reports_ok():
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_compile_route_generates_prompt_from_supplied_grammar():
    response = client.post(
        "/api/compile",
        json={
            "shot_grammar": [
                {
                    "shot_id": "S01",
                    "time_range": {"start": 0.0, "end": 3.0, "duration": 3.0},
                    "shot_type": "transferable dramatic beat",
                    "camera": {
                        "shot_size_start": "medium shot",
                        "shot_size_end": "close-up",
                        "angle": "eye-level",
                        "movement": "slow push-in",
                        "camera_energy": "slow and tense",
                    },
                    "composition": {
                        "main_subject_position": "foreground right",
                        "secondary_subject_position": "background left",
                        "spatial_relationship": "emotional distance",
                        "depth_structure": "foreground dominates",
                    },
                    "action_pattern": {
                        "start": "Character A pauses",
                        "middle": "Character A raises eyes",
                        "end": "Character B delays reaction",
                    },
                    "emotion_pattern": {
                        "start": "suppressed emotion",
                        "middle": "tension increases",
                        "end": "unresolved pressure",
                    },
                    "editing_function": "establish conflict",
                    "continuity_rule": "maintain tension",
                    "replaceable_variables": {
                        "character_a": "any pressured character",
                        "character_b": "any silent character",
                        "location": "any tense space",
                        "prop": "optional pressure prop",
                    },
                    "prompt_pattern": "Keep the same shot grammar.",
                }
            ],
            "new_content": {
                "target_style": "AI 漫剧",
                "new_story": "雨夜质问背叛",
                "character_a": "年轻女赏金猎人",
                "character_b": "机械改造男性",
                "location": "赛博朋克雨夜巷道",
                "aspect_ratio": "9:16",
                "video_model": "Seedance",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["generated_prompts"][0]["shot_id"] == "S01"
    assert "年轻女赏金猎人" in payload["generated_prompts"][0]["prompt"]


def test_replicate_route_generates_seedance_prompt_from_supplied_grammar():
    response = client.post(
        "/api/replicate",
        json={
            "shot_grammar": [
                {
                    "shot_id": "S01",
                    "time_range": {"start": 0.0, "end": 3.0, "duration": 3.0},
                    "shot_type": "Extreme Wide Shot",
                    "camera": {
                        "angle": "Low Angle",
                        "movement": "Static / Slight Push In",
                    },
                    "composition": {
                        "foreground": "Massive foreground monster feet",
                        "background": "Stormy mountain ridge",
                    },
                    "action_pattern": {
                        "start": "Small figure holds still",
                        "middle": "Mist moves slowly",
                        "end": "Threat remains unresolved",
                    },
                    "emotion_pattern": {
                        "atmosphere": "Foreboding and epic",
                    },
                    "editing_function": "Establish scale",
                    "continuity_rule": "Maintain spatial orientation",
                    "replaceable_variables": {},
                    "prompt_pattern": "Massive foreground monster feet, tiny figure far away.",
                }
            ],
            "aspect_ratio": "16:9",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    prompt = payload["generated_prompts"][0]["prompt"]
    assert payload["mode"] == "replicate"
    assert payload["video_model"] == "Seedance 2.0"
    assert "Massive foreground monster feet" in prompt
    assert "16:9" in prompt


def test_video_replicate_llm_route_reads_analysis_and_saves_prompts(tmp_path, monkeypatch):
    from app import server
    from app.config import AppConfig
    from app.harness import ReplicationHarness

    class FakeLLMClient:
        def analyze(self, messages):
            return {
                "seedance_prompt": "Seedance 2.0 复刻：风暴山脊上的低机位巨物压迫镜头。",
                "negative_prompt": "不要改变低机位、风暴山脊和尺度压迫。",
                "source_reasoning": "保留原镜头的低机位、前景巨物和远景人物。",
            }

    seen = {}

    class FakeCompiler:
        def compile_replicate_with_llm(self, grammars, client, aspect_ratio, max_workers=4):
            seen["max_workers"] = max_workers
            return {
                "mode": "replicate_llm",
                "video_model": "Seedance 2.0",
                "generated_prompts": [
                    {
                        "shot_id": "S01",
                        "duration": "3s",
                        "prompt": "Seedance 2.0 复刻：风暴山脊上的低机位巨物压迫镜头。",
                        "seedance_prompt": "Seedance 2.0 复刻：风暴山脊上的低机位巨物压迫镜头。",
                        "negative_prompt": "不要改变低机位、风暴山脊和尺度压迫。",
                        "source_reasoning": "保留原镜头的低机位、前景巨物和远景人物。",
                    }
                ],
            }

    monkeypatch.setattr(server, "config", AppConfig(data_root=tmp_path))
    monkeypatch.setattr(server, "_build_vlm_client", lambda: FakeLLMClient())
    monkeypatch.setattr(server, "compiler", FakeCompiler())
    video_dir = tmp_path / "videos" / "vid123"
    video_dir.mkdir(parents=True)
    (video_dir / "replication_state.json").write_text(
        """
        {
          "project_id": "vid123",
          "source_video": "source.mp4",
          "current_stage": "shot_language_loop_completed",
          "next_action": "generate_seedance_prompt",
          "errors": [],
          "artifacts": {
            "analysis": "analysis.json",
            "shot_list": "shot_list.json",
            "replication_state": "replication_state.json"
          },
          "loops": []
        }
        """,
        encoding="utf-8",
    )
    (video_dir / "analysis.json").write_text(
        """
        {
          "video_info": {"aspect_ratio": "16:9"},
          "shot_grammar": [
            {
              "shot_id": "S01",
              "time_range": {"start": 0.0, "end": 3.0, "duration": 3.0},
              "shot_type": "Extreme Wide Shot",
              "camera": {"angle": "Low Angle", "movement": "Static"},
              "composition": {"foreground": "Massive monster feet", "background": "Stormy ridge"},
              "action_pattern": {"start": "Small figure stands still"},
              "emotion_pattern": {"atmosphere": "Epic oppression"},
              "editing_function": "Establish scale",
              "continuity_rule": "Maintain spatial orientation",
              "replaceable_variables": {},
              "prompt_pattern": "Low angle giant foreground and tiny figure."
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    response = client.post("/api/videos/vid123/replicate/llm", json={"max_workers": 3})

    assert response.status_code == 200
    payload = response.json()
    saved = video_dir / "replicate_prompts.json"
    assert payload["mode"] == "replicate_llm"
    assert payload["generated_prompts"][0]["shot_id"] == "S01"
    assert "风暴山脊" in payload["generated_prompts"][0]["prompt"]
    assert seen["max_workers"] == 3
    assert saved.exists()
    assert "replicate_llm" in saved.read_text(encoding="utf-8")
    state = (video_dir / "replication_state.json").read_text(encoding="utf-8")
    assert "prompt_generation_loop" in state
    assert "review_generated_prompts" in state


def test_latest_analysis_route_returns_most_recent_existing_analysis(tmp_path, monkeypatch):
    from app import server
    from app.config import AppConfig

    monkeypatch.setattr(server, "config", AppConfig(data_root=tmp_path))
    older_dir = tmp_path / "videos" / "older"
    newer_dir = tmp_path / "videos" / "newer"
    older_dir.mkdir(parents=True)
    newer_dir.mkdir(parents=True)
    (older_dir / "source.mp4").write_bytes(b"mp4")
    (newer_dir / "source.mp4").write_bytes(b"mp4")
    (older_dir / "analysis.json").write_text(
        '{"video_info":{"duration":1},"shots":[],"shot_grammar":[]}',
        encoding="utf-8",
    )
    newer_analysis = newer_dir / "analysis.json"
    newer_analysis.write_text(
        '{"video_info":{"duration":2},"shots":[{"shot_id":"S01"}],"shot_grammar":[]}',
        encoding="utf-8",
    )
    import os
    os.utime(older_dir / "analysis.json", (1000, 1000))
    os.utime(newer_analysis, (2000, 2000))

    response = client.get("/api/videos/latest-analysis")

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == "newer"
    assert payload["analysis"]["video_info"]["duration"] == 2


def test_upload_route_rejects_non_mp4_file():
    response = client.post(
        "/api/upload",
        files={"file": ("clip.txt", b"not a video", "text/plain")},
    )

    assert response.status_code == 400
    assert "mp4" in response.json()["detail"]


def test_media_routes_return_uploaded_video_and_keyframes(tmp_path, monkeypatch):
    from app import server
    from app.config import AppConfig

    monkeypatch.setattr(server, "config", AppConfig(data_root=tmp_path))
    video_dir = tmp_path / "videos" / "vid123"
    shot_dir = video_dir / "shots" / "S01"
    shot_dir.mkdir(parents=True)
    (video_dir / "source.mp4").write_bytes(b"mp4")
    (shot_dir / "frame_start.jpg").write_bytes(b"jpg")

    video_response = client.get("/api/videos/vid123/media/source")
    frame_response = client.get("/api/videos/vid123/shots/S01/frame_start.jpg")

    assert video_response.status_code == 200
    assert frame_response.status_code == 200


def test_analyze_job_route_returns_immediate_status_and_result(tmp_path, monkeypatch):
    from app import server
    from app.config import AppConfig
    from app.harness import ReplicationHarness

    class FakePipeline:
        def analyze(self, source_path, shots_dir, progress_callback=None, partial_callback=None):
            if progress_callback:
                progress_callback(
                    {
                        "stage": "completed",
                        "message": "分析完成",
                        "progress": 100,
                        "current": 0,
                        "total": 0,
                    }
                )
            result = {
                "video_info": {
                    "duration": 1.0,
                    "fps": 24.0,
                    "width": 360,
                    "height": 640,
                    "aspect_ratio": "9:16",
                    "has_audio": False,
                },
                "candidate_shots": [
                    {"shot_id": "S01", "start_time": 0, "end_time": 1, "duration": 1}
                ],
                "scenes": [
                    {
                        "scene_id": "SC01",
                        "start_time": 0,
                        "end_time": 1,
                        "duration": 1,
                        "shot_ids": ["S01"],
                        "summary": "test scene",
                    }
                ],
                "shots": [{"shot_id": "S01", "start_time": 0, "end_time": 1, "duration": 1}],
                "context_tracks": {
                    "speech": {"enabled": False, "provider": None, "segments": []},
                    "ocr": {"enabled": False, "provider": None, "segments": []},
                },
                "keyframes": [],
                "shot_grammar": [{"shot_id": "S01", "shot_type": "test"}],
                "video_structure": {"video_structure": {"total_shots": 1}},
            }
            if partial_callback:
                partial_callback(
                    {
                        "status": "partial",
                        "video_info": result["video_info"],
                        "candidate_shots": result["candidate_shots"],
                        "scenes": result["scenes"],
                        "shots": result["shots"],
                        "context_tracks": result["context_tracks"],
                        "keyframes": result["keyframes"],
                        "shot": result["shots"][0],
                        "grammar": result["shot_grammar"][0],
                        "shot_grammar": result["shot_grammar"],
                    }
                )
            return {
                **result,
            }

    monkeypatch.setattr(server, "config", AppConfig(data_root=tmp_path))
    monkeypatch.setattr(server, "pipeline", FakePipeline())
    monkeypatch.setattr(server, "harness", ReplicationHarness(pipeline=FakePipeline()))
    video_dir = tmp_path / "videos" / "vid123"
    video_dir.mkdir(parents=True)
    (video_dir / "source.mp4").write_bytes(b"mp4")

    start_response = client.post("/api/videos/vid123/analyze/start")

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]
    status_response = client.get(f"/api/analysis-jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert status_response.json()["result"]["video_info"]["duration"] == 1.0
    assert (video_dir / "analysis.partial.json").exists()
    assert (video_dir / "replication_state.json").exists()
    assert (video_dir / "shot_list.json").exists()
    shot_list = (video_dir / "shot_list.json").read_text(encoding="utf-8")
    assert "context_tracks" in shot_list
    assert "SC01" in shot_list
    assert (video_dir / "shots" / "S01" / "shot_grammar.json").exists()
