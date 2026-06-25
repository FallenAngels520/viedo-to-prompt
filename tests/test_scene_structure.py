from app.models import Shot
from app.scene_structure import SceneStructureService


def test_scene_structure_service_groups_final_shots_into_default_scene():
    service = SceneStructureService()

    scenes = service.group(
        [
            Shot("S01", 0.0, 2.0, 2.0),
            Shot("S02", 2.0, 5.0, 3.0),
        ]
    )

    assert scenes == [
        {
            "scene_id": "SC01",
            "start_time": 0.0,
            "end_time": 5.0,
            "duration": 5.0,
            "shot_ids": ["S01", "S02"],
            "summary": "Default scene group for the analyzed video.",
        }
    ]
