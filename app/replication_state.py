from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.shot_language_loop import ShotLanguageLoopEvaluator


class ReplicationStateStore:
    def record_prompt_generation(
        self,
        video_dir: Path,
        prompts: dict[str, Any],
        artifact_name: str = "replicate_prompts.json",
    ) -> dict[str, Any]:
        state_path = video_dir / "replication_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
        else:
            state = {
                "project_id": video_dir.name,
                "source_video": str(video_dir / "source.mp4"),
                "errors": [],
                "artifacts": {},
                "loops": [],
            }
        state["current_stage"] = "prompt_generation_loop_completed"
        state["next_action"] = "review_generated_prompts"
        state.setdefault("artifacts", {})["replicate_prompts"] = artifact_name
        state.setdefault("loops", []).append(
            {
                "name": "prompt_generation_loop",
                "status": "completed",
                "inputs": {
                    "shot_grammar": "analysis.json#/shot_grammar",
                },
                "outputs": {
                    "replicate_prompts": artifact_name,
                },
                "evaluation": {
                    "prompt_count": len(prompts.get("generated_prompts", [])),
                    "manual_review_required": True,
                },
                "corrections": [],
            }
        )
        state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return state

    def write_completed_loop1(
        self,
        project_id: str,
        video_dir: Path,
        source_video: Path,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        state = self.build_completed_loop1(project_id, source_video, result)
        (video_dir / "replication_state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return state

    def build_completed_loop1(
        self,
        project_id: str,
        source_video: Path,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        language_evaluation = ShotLanguageLoopEvaluator().evaluate(
            result.get("shot_grammar", [])
        )
        return {
            "project_id": project_id,
            "source_video": str(source_video),
            "current_stage": "shot_language_loop_completed",
            "next_action": "generate_seedance_prompt",
            "candidate_shots": result.get("candidate_shots", []),
            "scenes": result.get("scenes", []),
            "shots": [
                self._shot_state(shot, language_evaluation)
                for shot in result.get("shots", [])
            ],
            "context_tracks": result.get("context_tracks", {}),
            "errors": [],
            "artifacts": {
                "analysis": "analysis.json",
                "shot_list": "shot_list.json",
                "replication_state": "replication_state.json",
                "shots_dir": "shots",
            },
            "loops": [
                {
                    "name": "shot_detection_loop",
                    "status": "completed",
                    "inputs": {
                        "source_video": str(source_video),
                    },
                    "outputs": {
                        "analysis": "analysis.json",
                        "shot_list": "shot_list.json",
                        "replication_state": "replication_state.json",
                        "shots_dir": "shots",
                    },
                    "evaluation": {
                        "candidate_shot_count": len(result.get("candidate_shots", [])),
                        "final_shot_count": len(result.get("shots", [])),
                        "scene_count": len(result.get("scenes", [])),
                        "manual_review_required": True,
                    },
                    "corrections": [],
                },
                {
                    "name": "shot_language_loop",
                    "status": "completed",
                    "inputs": {
                        "shot_grammar": "analysis.json#/shot_grammar",
                    },
                    "outputs": {
                        "shot_language_evaluation": "replication_state.json#/loops/1/evaluation",
                    },
                    "evaluation": language_evaluation["summary"],
                    "corrections": [
                        {
                            "shot_id": item["shot_id"],
                            "reason": "missing required shot grammar fields",
                            "missing_fields": item["missing_fields"],
                        }
                        for item in language_evaluation["items"]
                        if item["status"] == "needs_review"
                    ],
                },
            ],
        }

    def _shot_state(
        self,
        shot: dict[str, Any],
        language_evaluation: dict[str, Any],
    ) -> dict[str, Any]:
        language_by_shot = {
            item["shot_id"]: item for item in language_evaluation.get("items", [])
        }
        language = language_by_shot.get(shot.get("shot_id"), {})
        status = language.get("status", "verified")
        return {
            **shot,
            "status": status,
            "need_split": False,
            "need_merge": False,
            "needs_review": status == "needs_review",
            "analysis_quality": language.get("analysis_quality"),
            "missing_grammar_fields": language.get("missing_fields", []),
            "errors": [],
        }
