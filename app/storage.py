from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models import VideoWorkspace


class VideoStorage:
    def __init__(self, data_root: Path | str = "data") -> None:
        self.data_root = Path(data_root)

    def create_workspace(self, original_filename: str) -> VideoWorkspace:
        suffix = Path(original_filename).suffix.lower()
        if suffix != ".mp4":
            raise ValueError("Only .mp4 uploads are supported")

        video_id = uuid4().hex[:12]
        video_dir = self.data_root / "videos" / video_id
        shots_dir = video_dir / "shots"
        shots_dir.mkdir(parents=True, exist_ok=False)
        return VideoWorkspace(
            video_id=video_id,
            video_dir=video_dir,
            source_path=video_dir / "source.mp4",
            shots_dir=shots_dir,
        )

