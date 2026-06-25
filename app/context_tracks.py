from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models import Shot


class ContextTrackService:
    """Extension point for future speech and OCR alignment.

    The default implementation intentionally performs no recognition.
    """

    def extract(self, video_path: Path, shots: list[Shot]) -> dict[str, Any]:
        del video_path, shots
        return {
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
