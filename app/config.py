from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class AppConfig:
    data_root: Path = Path("data")
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    vlm_api_base: str | None = None
    vlm_api_key: str | None = None
    vlm_model: str | None = None


def load_config() -> AppConfig:
    env_file = dotenv_values(".env") if Path(".env").exists() else {}
    ffmpeg = (
        _env("FFMPEG_PATH", env_file)
        or shutil.which("ffmpeg")
        or _remotion_tool("ffmpeg.exe")
        or "ffmpeg"
    )
    ffprobe = (
        _env("FFPROBE_PATH", env_file)
        or shutil.which("ffprobe")
        or _remotion_tool("ffprobe.exe")
        or "ffprobe"
    )
    return AppConfig(
        data_root=Path(_env("VIDEO_PROMPT_DATA", env_file) or "data"),
        ffmpeg_path=ffmpeg,
        ffprobe_path=ffprobe,
        vlm_api_base=_env("VLM_API_BASE", env_file),
        vlm_api_key=_env("VLM_API_KEY", env_file),
        vlm_model=_env("VLM_MODEL", env_file),
    )


def _env(key: str, env_file: dict[str, str | None]) -> str | None:
    return os.environ.get(key) or env_file.get(key)


def _remotion_tool(filename: str) -> str | None:
    candidate = (
        Path("E:/code/remotion-dev/node_modules/@remotion/compositor-win32-x64-msvc")
        / filename
    )
    return str(candidate) if candidate.exists() else None
