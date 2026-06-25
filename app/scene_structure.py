from __future__ import annotations

from typing import Any

from app.models import Shot


class SceneStructureService:
    """Extension point for narrative scene grouping."""

    def group(self, shots: list[Shot]) -> list[dict[str, Any]]:
        if not shots:
            return []
        start_time = shots[0].start_time
        end_time = shots[-1].end_time
        return [
            {
                "scene_id": "SC01",
                "start_time": start_time,
                "end_time": end_time,
                "duration": round(end_time - start_time, 3),
                "shot_ids": [shot.shot_id for shot in shots],
                "summary": "Default scene group for the analyzed video.",
            }
        ]
