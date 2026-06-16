from __future__ import annotations

import base64
from statistics import mean
from typing import Any

from app.models import Keyframes, Shot, ShotGrammar


class ShotGrammarAnalyzer:
    """Deterministic local analyzer used until a real VLM provider is configured."""

    def analyze(self, shot: Shot, keyframes: Keyframes) -> ShotGrammar:
        del keyframes
        return ShotGrammar(
            shot_id=shot.shot_id,
            time_range={
                "start": shot.start_time,
                "end": shot.end_time,
                "duration": shot.duration,
            },
            shot_type="transferable dramatic beat",
            camera={
                "shot_size_start": "medium shot",
                "shot_size_end": "close-up",
                "angle": "eye-level",
                "movement": "slow push-in",
                "camera_energy": "slow and tense",
            },
            composition={
                "main_subject_position": "foreground right or center",
                "secondary_subject_position": "background left or opposite side",
                "spatial_relationship": "two characters held apart by emotional distance",
                "depth_structure": "foreground subject leads, background subject adds tension",
            },
            action_pattern={
                "start": "Character A holds still before acting",
                "middle": "Character A slowly shifts gaze or posture",
                "end": "Character B delays reaction to preserve tension",
            },
            emotion_pattern={
                "start": "suppressed emotion",
                "middle": "tension increases",
                "end": "unresolved emotional pressure",
            },
            editing_function="establish or continue conflict while preserving suspense",
            continuity_rule=(
                "next shot should maintain emotional tension, spatial relationship, "
                "and restrained movement"
            ),
            replaceable_variables={
                "character_a": "any questioning, vulnerable or emotionally pressured character",
                "character_b": "any evasive, powerful or silent character",
                "location": "any tense enclosed, semi-enclosed or confrontational space",
                "prop": "optional object that can show emotional pressure",
            },
            prompt_pattern=(
                "Use a medium shot that slowly pushes toward Character A. Keep Character A "
                "dominant in the foreground and Character B separated in the background. "
                "Let Character A pause, then shift gaze or posture. Let Character B delay "
                "their reaction. Maintain emotional tension and spatial distance."
            ),
        )


class VLMShotGrammarAnalyzer:
    def __init__(self, client: Any) -> None:
        self.client = client

    def analyze(self, shot: Shot, keyframes: Keyframes) -> ShotGrammar:
        payload = self.client.analyze(self._build_messages(shot, keyframes))
        return ShotGrammar(**self._normalize_payload(payload, shot))

    def _build_messages(self, shot: Shot, keyframes: Keyframes) -> list[dict[str, Any]]:
        prompt = (
            "你是影视镜头语法分析器。不要复述具体人物身份、场景名称、台词或剧情，"
            "只提取可迁移的镜头结构。必须输出 JSON，字段必须包含：shot_id, "
            "time_range, shot_type, camera, composition, action_pattern, "
            "emotion_pattern, editing_function, continuity_rule, "
            "replaceable_variables, prompt_pattern。camera、composition、action_pattern、"
            "emotion_pattern、replaceable_variables 必须是对象，不能是字符串。time_range "
            "必须是包含 start、end、duration 的对象。"
        )
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"分析镜头 {shot.shot_id}，时间范围 {shot.start_time}-{shot.end_time} 秒，"
                    f"时长 {shot.duration} 秒。"
                ),
            }
        ]
        for frame_path in [
            keyframes.frame_start,
            keyframes.frame_mid,
            keyframes.frame_end,
        ]:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{_encode_image(frame_path)}"
                    },
                }
            )
        return [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ]

    def _normalize_payload(self, payload: dict[str, Any], shot: Shot) -> dict[str, Any]:
        local = ShotGrammarAnalyzer().analyze(shot, Keyframes(
            shot_id=shot.shot_id,
            frame_start=None,
            frame_mid=None,
            frame_end=None,
            timestamps={},
        )).to_dict()
        normalized = dict(payload)
        normalized["shot_id"] = shot.shot_id
        if not isinstance(normalized.get("time_range"), dict):
            normalized["time_range"] = local["time_range"]
        normalized["camera"] = _object_or_fallback(
            normalized.get("camera"),
            local["camera"],
            "movement",
        )
        normalized["composition"] = _object_or_fallback(
            normalized.get("composition"),
            local["composition"],
            "spatial_relationship",
        )
        normalized["action_pattern"] = _object_or_fallback(
            normalized.get("action_pattern"),
            local["action_pattern"],
            "middle",
        )
        normalized["emotion_pattern"] = _object_or_fallback(
            normalized.get("emotion_pattern"),
            local["emotion_pattern"],
            "middle",
        )
        normalized["replaceable_variables"] = _merge_object(
            normalized.get("replaceable_variables"),
            local["replaceable_variables"],
        )
        for key in [
            "shot_type",
            "editing_function",
            "continuity_rule",
            "prompt_pattern",
        ]:
            if not isinstance(normalized.get(key), str):
                normalized[key] = local[key]
        return normalized


def _encode_image(path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _object_or_fallback(value: Any, fallback: dict[str, str], preferred_key: str) -> dict[str, str]:
    if isinstance(value, dict):
        return _merge_object(value, fallback)
    merged = dict(fallback)
    if isinstance(value, str) and value.strip():
        merged[preferred_key] = value
    return merged


def _merge_object(value: Any, fallback: dict[str, str]) -> dict[str, str]:
    merged = dict(fallback)
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and item.strip():
                merged[key] = item
    return merged


class VideoStructureSummarizer:
    def summarize(self, grammars: list[ShotGrammar]) -> dict[str, dict[str, object]]:
        durations = [grammar.time_range["duration"] for grammar in grammars]
        shot_types = list(dict.fromkeys(grammar.shot_type for grammar in grammars))
        return {
            "video_structure": {
                "total_shots": len(grammars),
                "average_shot_duration": round(mean(durations), 3) if durations else 0,
                "editing_rhythm": "slow emotional build-up with clear shot beats",
                "camera_style": "stable cinematic camera with slow push-ins and reaction beats",
                "dominant_shot_types": shot_types,
                "emotional_curve": "suppression -> tension -> delayed reaction -> unresolved hook",
            }
        }
