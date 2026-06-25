from pathlib import Path

from app.replication_state import ReplicationStateStore
from app.harness import ReplicationHarness


class FakePipeline:
    def analyze(self, source_path, shots_dir, progress_callback=None, partial_callback=None):
        if progress_callback:
            progress_callback({"stage": "shot_detection", "progress": 15})
        return {
            "video_info": {"duration": 2.0, "aspect_ratio": "9:16"},
            "candidate_shots": [
                {"shot_id": "S01", "start_time": 0.0, "end_time": 2.0, "duration": 2.0}
            ],
            "scenes": [
                {
                    "scene_id": "SC01",
                    "start_time": 0.0,
                    "end_time": 2.0,
                    "duration": 2.0,
                    "shot_ids": ["S01"],
                    "summary": "test scene",
                }
            ],
            "shots": [
                {"shot_id": "S01", "start_time": 0.0, "end_time": 2.0, "duration": 2.0}
            ],
            "context_tracks": {
                "speech": {"enabled": False, "provider": None, "segments": []},
                "ocr": {"enabled": False, "provider": None, "segments": []},
            },
            "keyframes": [],
            "shot_grammar": [{"shot_id": "S01", "shot_type": "medium shot"}],
            "video_structure": {"video_structure": {"total_shots": 1}},
        }


def test_replication_state_store_writes_loop_state(tmp_path):
    result = FakePipeline().analyze(tmp_path / "source.mp4", tmp_path / "shots")

    state = ReplicationStateStore().write_completed_loop1(
        project_id="vid123",
        video_dir=tmp_path,
        source_video=tmp_path / "source.mp4",
        result=result,
    )

    saved = tmp_path / "replication_state.json"
    assert saved.exists()
    assert state["project_id"] == "vid123"
    assert state["current_stage"] == "shot_language_loop_completed"
    assert state["next_action"] == "generate_seedance_prompt"
    assert state["errors"] == []
    assert state["artifacts"]["shot_list"] == "shot_list.json"
    assert state["loops"][0]["name"] == "shot_detection_loop"
    assert state["loops"][0]["status"] == "completed"
    assert state["loops"][0]["inputs"]["source_video"] == str(tmp_path / "source.mp4")
    assert state["loops"][0]["outputs"]["shot_list"] == "shot_list.json"
    assert state["loops"][0]["evaluation"]["manual_review_required"] is True
    assert state["loops"][0]["corrections"] == []
    assert state["loops"][1]["name"] == "shot_language_loop"
    assert state["loops"][1]["status"] == "completed"
    assert state["loops"][1]["evaluation"]["grammar_count"] == 1
    assert state["shots"][0]["status"] == "needs_review"
    assert state["shots"][0]["analysis_quality"] == 0.2
    assert state["shots"][0]["missing_grammar_fields"]


def test_replication_harness_runs_loop1_and_persists_state(tmp_path):
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"mp4")
    shots_dir = tmp_path / "shots"
    shots_dir.mkdir()
    events = []

    result = ReplicationHarness(pipeline=FakePipeline()).run_loop1(
        project_id="vid123",
        video_dir=tmp_path,
        source_path=source_path,
        shots_dir=shots_dir,
        progress_callback=events.append,
    )

    assert result["shots"][0]["shot_id"] == "S01"
    assert events == [{"stage": "shot_detection", "progress": 15}]
    assert (tmp_path / "replication_state.json").exists()
