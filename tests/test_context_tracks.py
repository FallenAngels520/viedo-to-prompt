from pathlib import Path

from app.context_tracks import ContextTrackService
from app.models import Shot


def test_context_track_service_returns_disabled_empty_tracks_by_default():
    service = ContextTrackService()

    result = service.extract(
        Path("source.mp4"),
        [
            Shot("S01", 0.0, 2.0, 2.0),
            Shot("S02", 2.0, 4.0, 2.0),
        ],
    )

    assert result == {
        "speech": {
            "enabled": False,
            "provider": None,
            "segments": [],
        },
        "ocr": {
            "enabled": False,
            "provider": None,
            "segments": [],
        },
    }
