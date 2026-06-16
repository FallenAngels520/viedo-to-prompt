from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VideoWorkspace:
    video_id: str
    video_dir: Path
    source_path: Path
    shots_dir: Path


@dataclass(frozen=True)
class VideoInfo:
    duration: float
    fps: float
    width: int
    height: int
    aspect_ratio: str
    has_audio: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Shot:
    shot_id: str
    start_time: float
    end_time: float
    duration: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Keyframes:
    shot_id: str
    frame_start: Path
    frame_mid: Path
    frame_end: Path
    timestamps: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "frame_start": str(self.frame_start),
            "frame_mid": str(self.frame_mid),
            "frame_end": str(self.frame_end),
            "timestamps": self.timestamps,
        }


@dataclass(frozen=True)
class ShotGrammar:
    shot_id: str
    time_range: dict[str, float]
    shot_type: str
    camera: dict[str, str]
    composition: dict[str, str]
    action_pattern: dict[str, str]
    emotion_pattern: dict[str, str]
    editing_function: str
    continuity_rule: str
    replaceable_variables: dict[str, str]
    prompt_pattern: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NewContentInput:
    target_style: str
    new_story: str
    character_a: str
    character_b: str
    location: str
    aspect_ratio: str
    video_model: str

