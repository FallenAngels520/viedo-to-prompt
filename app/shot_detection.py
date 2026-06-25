from __future__ import annotations

import re
import subprocess
from pathlib import Path

from app.logging_config import logger
from app.models import Shot


class ShotDetectionService:
    def __init__(
        self,
        ffmpeg_path: str | None = None,
        scene_threshold: float = 0.35,
        fallback_seconds: float = 3.0,
        opencv_threshold: float = 65.0,
        opencv_min_gap_seconds: float = 3.0,
        opencv_sample_seconds: float = 0.5,
        use_pyscenedetect: bool = True,
        pyscene_threshold: float = 27.0,
    ) -> None:
        self.ffmpeg_path = ffmpeg_path or "ffmpeg"
        self.scene_threshold = scene_threshold
        self.fallback_seconds = fallback_seconds
        self.opencv_threshold = opencv_threshold
        self.opencv_min_gap_seconds = opencv_min_gap_seconds
        self.opencv_sample_seconds = opencv_sample_seconds
        self.use_pyscenedetect = use_pyscenedetect
        self.pyscene_threshold = pyscene_threshold

    def detect(self, video_path: Path, duration: float) -> list[Shot]:
        cuts: list[float] = []
        if self.use_pyscenedetect:
            try:
                cuts = self._detect_cut_times_pyscenedetect(video_path)
            except (ImportError, RuntimeError) as exc:
                logger.warning("shot_detection_pyscenedetect_failed fallback=ffmpeg error=%s", exc)
        if cuts:
            return self._shots_from_cut_times(cuts, duration)

        try:
            cuts = self._detect_cut_times(video_path)
        except (FileNotFoundError, RuntimeError, subprocess.SubprocessError) as exc:
            logger.warning("shot_detection_ffmpeg_failed fallback=opencv error=%s", exc)
            try:
                cuts = self._detect_cut_times_opencv(video_path, duration)
            except (ImportError, RuntimeError) as opencv_exc:
                logger.warning(
                    "shot_detection_opencv_failed fallback=fixed_segments error=%s",
                    opencv_exc,
                )
                return self.fallback_segments(duration)

        return self._shots_from_cut_times(cuts, duration)

    def _shots_from_cut_times(self, cuts: list[float], duration: float) -> list[Shot]:
        times = [0.0] + [time for time in cuts if 0.0 < time < duration] + [duration]
        unique_times = sorted(set(round(time, 3) for time in times))
        if len(unique_times) <= 2:
            logger.warning("shot_detection_no_cuts fallback=fixed_segments duration=%s", duration)
            return self.fallback_segments(duration)
        return self._shots_from_boundaries(unique_times)

    def fallback_segments(self, duration: float) -> list[Shot]:
        if duration <= 0:
            return []
        boundaries = [0.0]
        cursor = self.fallback_seconds
        while cursor < duration:
            boundaries.append(round(cursor, 3))
            cursor += self.fallback_seconds
        boundaries.append(round(duration, 3))
        return self._shots_from_boundaries(boundaries)

    def _detect_cut_times(self, video_path: Path) -> list[float]:
        command = self.build_detection_command(video_path)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = completed.stderr + completed.stdout
        if completed.returncode != 0:
            raise RuntimeError(output.strip() or "ffmpeg shot detection failed")
        return [float(value) for value in re.findall(r"pts_time:([0-9.]+)", output)]

    def _detect_cut_times_pyscenedetect(self, video_path: Path) -> list[float]:
        try:
            from scenedetect import ContentDetector, detect
        except ImportError as exc:
            raise ImportError("PySceneDetect is not installed") from exc

        try:
            scenes = detect(str(video_path), ContentDetector(threshold=self.pyscene_threshold))
        except Exception as exc:
            raise RuntimeError(f"PySceneDetect failed: {exc}") from exc

        cuts: list[float] = []
        for index, (start_time, _end_time) in enumerate(scenes):
            if index == 0:
                continue
            cuts.append(round(float(start_time.get_seconds()), 3))
        return cuts

    def build_detection_command(self, video_path: Path) -> list[str]:
        return [
            self.ffmpeg_path,
            "-i",
            str(video_path),
            "-an",
            "-filter:v",
            f"select=gt(scene\\,{self.scene_threshold}),showinfo",
            "-c:v",
            "png",
            "-f",
            "image2pipe",
            "-",
        ]

    def _detect_cut_times_opencv(self, video_path: Path, duration: float) -> list[float]:
        try:
            import cv2
        except ImportError as exc:
            raise ImportError("opencv-python is not installed") from exc

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError(f"OpenCV could not open video: {video_path}")

        scores: list[tuple[float, float]] = []
        previous_frame = None
        timestamp = 0.0
        try:
            while timestamp < duration:
                capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                ok, frame = capture.read()
                if not ok:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.resize(gray, (160, 90))
                if previous_frame is not None:
                    diff = cv2.absdiff(gray, previous_frame)
                    scores.append((round(timestamp, 3), float(diff.mean())))
                previous_frame = gray
                timestamp += self.opencv_sample_seconds
        finally:
            capture.release()

        return self._cut_times_from_frame_scores(scores)

    def _cut_times_from_frame_scores(self, scores: list[tuple[float, float]]) -> list[float]:
        cuts: list[float] = []
        last_cut = -self.opencv_min_gap_seconds
        for timestamp, score in scores:
            if score < self.opencv_threshold:
                continue
            if timestamp - last_cut < self.opencv_min_gap_seconds:
                continue
            cuts.append(round(timestamp, 3))
            last_cut = timestamp
        return cuts

    def _shots_from_boundaries(self, boundaries: list[float]) -> list[Shot]:
        shots: list[Shot] = []
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), start=1):
            if end <= start:
                continue
            duration = round(end - start, 3)
            shots.append(
                Shot(
                    shot_id=f"S{index:02d}",
                    start_time=round(start, 3),
                    end_time=round(end, 3),
                    duration=duration,
                )
            )
        return shots
