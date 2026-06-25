from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.keyframes import KeyframeService
from app.models import Keyframes, Shot


@dataclass(frozen=True)
class CandidateShotDecision:
    same_shot: bool = True
    need_split: bool = False
    possible_split: str = ""
    reason: str = ""


@dataclass(frozen=True)
class TransitionDecision:
    is_true_cut: bool = True
    reason: str = ""


class DeterministicShotBoundaryValidator:
    def validate_candidate(self, shot: Shot, keyframes: Keyframes) -> CandidateShotDecision:
        del shot, keyframes
        return CandidateShotDecision()

    def validate_transition(
        self,
        previous_shot: Shot,
        previous_keyframes: Keyframes,
        current_shot: Shot,
        current_keyframes: Keyframes,
    ) -> TransitionDecision:
        del previous_shot, previous_keyframes, current_shot, current_keyframes
        return TransitionDecision()


class VLMShotBoundaryValidator:
    def __init__(self, client: Any) -> None:
        self.client = client

    def validate_candidate(self, shot: Shot, keyframes: Keyframes) -> CandidateShotDecision:
        payload = self.client.analyze(self._candidate_messages(shot, keyframes))
        return CandidateShotDecision(
            same_shot=_bool(payload.get("same_shot"), True),
            need_split=_bool(payload.get("need_split"), False),
            possible_split=_text(payload.get("possible_split")),
            reason=_text(payload.get("reason")),
        )

    def validate_transition(
        self,
        previous_shot: Shot,
        previous_keyframes: Keyframes,
        current_shot: Shot,
        current_keyframes: Keyframes,
    ) -> TransitionDecision:
        payload = self.client.analyze(
            self._transition_messages(
                previous_shot,
                previous_keyframes,
                current_shot,
                current_keyframes,
            )
        )
        return TransitionDecision(
            is_true_cut=_bool(payload.get("is_true_cut"), True),
            reason=_text(payload.get("reason")),
        )

    def _candidate_messages(self, shot: Shot, keyframes: Keyframes) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "These are the start, middle, and end frames of one candidate shot. "
                    "Decide whether they belong to one continuous shot. If the candidate "
                    "contains an internal cut, mark need_split true and say whether the "
                    "split is between start frame and middle frame, or between middle "
                    "frame and end frame. Ignore flash/light/subtitle-only changes as "
                    "story shots. Output JSON with same_shot, need_split, possible_split, "
                    "and reason."
                ),
            },
            {
                "type": "text",
                "text": (
                    f"shot_id={shot.shot_id}, start={shot.start_time}, "
                    f"end={shot.end_time}, duration={shot.duration}"
                ),
            },
        ]
        for frame_path in [
            keyframes.frame_start,
            keyframes.frame_mid,
            keyframes.frame_end,
        ]:
            content.append(_image_content(frame_path))
        return [
            {"role": "system", "content": "You validate candidate video-shot boundaries."},
            {"role": "user", "content": content},
        ]

    def _transition_messages(
        self,
        previous_shot: Shot,
        previous_keyframes: Keyframes,
        current_shot: Shot,
        current_keyframes: Keyframes,
    ) -> list[dict[str, Any]]:
        content = [
            {
                "type": "text",
                "text": (
                    "Compare the previous candidate shot end frame with the next "
                    "candidate shot start frame. Decide whether this is a true cut or "
                    "an over-split of the same continuous shot. Output JSON with "
                    "is_true_cut and reason."
                ),
            },
            {
                "type": "text",
                "text": (
                    f"previous={previous_shot.shot_id} {previous_shot.start_time}-"
                    f"{previous_shot.end_time}; current={current_shot.shot_id} "
                    f"{current_shot.start_time}-{current_shot.end_time}"
                ),
            },
            _image_content(previous_keyframes.frame_end),
            _image_content(current_keyframes.frame_start),
        ]
        return [
            {"role": "system", "content": "You validate adjacent video-shot cuts."},
            {"role": "user", "content": content},
        ]


class ShotBoundaryRefiner:
    def __init__(
        self,
        validator: Any | None = None,
        keyframe_service: KeyframeService | None = None,
        min_duration_seconds: float = 0.3,
    ) -> None:
        self.validator = validator or DeterministicShotBoundaryValidator()
        self.keyframe_service = keyframe_service or KeyframeService()
        self.min_duration_seconds = min_duration_seconds

    def refine(self, video_path: Path, shots_dir: Path, candidate_shots: list[Shot]) -> list[Shot]:
        long_enough = [
            shot for shot in candidate_shots if shot.duration >= self.min_duration_seconds
        ]
        split_shots = self._split_candidates(video_path, shots_dir, long_enough)
        candidate_frames = self._extract_keyframes(video_path, shots_dir, split_shots)
        merged = self._merge_over_split_shots(split_shots, candidate_frames)
        return self._renumber(merged)

    def _split_candidates(
        self,
        video_path: Path,
        shots_dir: Path,
        shots: list[Shot],
    ) -> list[Shot]:
        refined: list[Shot] = []
        for shot in shots:
            keyframes = self.keyframe_service.extract(video_path, shots_dir, shot)
            decision = self.validator.validate_candidate(shot, keyframes)
            if decision.need_split or not decision.same_shot:
                refined.extend(self._split_shot(shot, decision.possible_split))
            else:
                refined.append(shot)
        return [shot for shot in refined if shot.duration >= self.min_duration_seconds]

    def _merge_over_split_shots(
        self,
        shots: list[Shot],
        keyframes: dict[str, Keyframes],
    ) -> list[Shot]:
        merged: list[Shot] = []
        for shot in shots:
            if not merged:
                merged.append(shot)
                continue
            previous = merged[-1]
            decision = self.validator.validate_transition(
                previous,
                keyframes[previous.shot_id],
                shot,
                keyframes[shot.shot_id],
            )
            if decision.is_true_cut:
                merged.append(shot)
            else:
                previous_keyframes = keyframes[previous.shot_id]
                current_keyframes = keyframes[shot.shot_id]
                merged[-1] = self._combine(previous, shot)
                keyframes[merged[-1].shot_id] = self._combine_keyframes(
                    merged[-1],
                    previous_keyframes,
                    current_keyframes,
                )
        return merged

    def _extract_keyframes(
        self,
        video_path: Path,
        shots_dir: Path,
        shots: list[Shot],
    ) -> dict[str, Keyframes]:
        return {
            shot.shot_id: self.keyframe_service.extract(video_path, shots_dir, shot)
            for shot in shots
        }

    def _split_shot(self, shot: Shot, possible_split: str) -> list[Shot]:
        midpoint = (shot.start_time + shot.end_time) / 2
        split_hint = possible_split.lower()
        if "start" in split_hint and "middle" in split_hint:
            split_time = (shot.start_time + midpoint) / 2
        elif "middle" in split_hint and "end" in split_hint:
            split_time = (midpoint + shot.end_time) / 2
        else:
            split_time = midpoint
        split_time = round(split_time, 3)
        return [
            self._shot(shot.shot_id, shot.start_time, split_time),
            self._shot(f"{shot.shot_id}_B", split_time, shot.end_time),
        ]

    def _combine(self, previous: Shot, current: Shot) -> Shot:
        return self._shot(previous.shot_id, previous.start_time, current.end_time)

    def _combine_keyframes(
        self,
        shot: Shot,
        previous_keyframes: Keyframes,
        current_keyframes: Keyframes,
    ) -> Keyframes:
        return Keyframes(
            shot_id=shot.shot_id,
            frame_start=previous_keyframes.frame_start,
            frame_mid=previous_keyframes.frame_mid,
            frame_end=current_keyframes.frame_end,
            timestamps={
                "start": previous_keyframes.timestamps["start"],
                "middle": round((shot.start_time + shot.end_time) / 2, 3),
                "end": current_keyframes.timestamps["end"],
            },
        )

    def _renumber(self, shots: list[Shot]) -> list[Shot]:
        return [
            self._shot(f"S{index:02d}", shot.start_time, shot.end_time)
            for index, shot in enumerate(shots, start=1)
        ]

    def _shot(self, shot_id: str, start_time: float, end_time: float) -> Shot:
        start = round(start_time, 3)
        end = round(end_time, 3)
        return Shot(shot_id=shot_id, start_time=start, end_time=end, duration=round(end - start, 3))


def _image_content(path: Path) -> dict[str, Any]:
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{_encode_image(path)}"},
    }


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    return fallback


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
