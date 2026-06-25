from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.models import Keyframes, Shot


class KeyframeService:
    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"

    def plan_keyframes(self, shots_dir: Path, shot: Shot) -> Keyframes:
        shot_dir = shots_dir / shot.shot_id
        end_timestamp = max(shot.start_time, shot.end_time - 0.04)
        timestamps = {
            "start": round(shot.start_time, 3),
            "middle": round((shot.start_time + shot.end_time) / 2, 3),
            "end": round(end_timestamp, 3),
        }
        return Keyframes(
            shot_id=shot.shot_id,
            frame_start=shot_dir / "frame_start.jpg",
            frame_mid=shot_dir / "frame_mid.jpg",
            frame_end=shot_dir / "frame_end.jpg",
            timestamps=timestamps,
        )

    def extract(self, video_path: Path, shots_dir: Path, shot: Shot) -> Keyframes:
        keyframes = self.plan_keyframes(shots_dir, shot)
        keyframes.frame_start.parent.mkdir(parents=True, exist_ok=True)
        targets = [
            (keyframes.timestamps["start"], keyframes.frame_start),
            (keyframes.timestamps["middle"], keyframes.frame_mid),
            (keyframes.timestamps["end"], keyframes.frame_end),
        ]
        for timestamp, output_path in targets:
            self._extract_one(video_path, timestamp, output_path)
        self._write_meta(shot, keyframes)
        return keyframes

    def _extract_one(self, video_path: Path, timestamp: float, output_path: Path) -> None:
        command = self.build_extract_command(video_path, timestamp, output_path)
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError(f"ffmpeg failed to extract keyframe: {completed.stderr}")

    def build_extract_command(
        self, video_path: Path, timestamp: float, output_path: Path
    ) -> list[str]:
        return [
            self.ffmpeg_path,
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-pix_fmt",
            "yuvj420p",
            "-q:v",
            "2",
            str(output_path),
        ]

    def _write_meta(self, shot: Shot, keyframes: Keyframes) -> None:
        meta_path = keyframes.frame_start.parent / "meta.json"
        payload = {
            "shot_id": shot.shot_id,
            "start_time": shot.start_time,
            "end_time": shot.end_time,
            "duration": shot.duration,
            "frames": {
                "start": keyframes.frame_start.name,
                "middle": keyframes.frame_mid.name,
                "end": keyframes.frame_end.name,
            },
            "timestamps": keyframes.timestamps,
        }
        meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
