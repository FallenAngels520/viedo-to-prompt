from __future__ import annotations

import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.models import VideoInfo


class VideoInfoService:
    def __init__(self, ffprobe_path: str | None = None) -> None:
        self.ffprobe_path = ffprobe_path or "ffprobe"

    def probe(self, video_path: Path) -> VideoInfo:
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {completed.stderr}")
        return self.from_ffprobe_json(json.loads(completed.stdout))

    def from_ffprobe_json(self, payload: dict[str, Any]) -> VideoInfo:
        streams = payload.get("streams", [])
        video_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "video"), None
        )
        if not video_stream:
            raise ValueError("No video stream found")

        duration = float(
            video_stream.get("duration")
            or payload.get("format", {}).get("duration")
            or 0.0
        )
        width = int(video_stream["width"])
        height = int(video_stream["height"])
        fps = _parse_fps(video_stream.get("avg_frame_rate") or "0/1")
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        return VideoInfo(
            duration=round(duration, 3),
            fps=round(fps, 3),
            width=width,
            height=height,
            aspect_ratio=_aspect_ratio(width, height),
            has_audio=has_audio,
        )


def _parse_fps(value: str) -> float:
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def _aspect_ratio(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "unknown"
    divisor = math.gcd(width, height)
    return f"{width // divisor}:{height // divisor}"

