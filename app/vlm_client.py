from __future__ import annotations

import json
from typing import Any

import requests

from app.logging_config import logger


class OpenAICompatibleVLMClient:
    def __init__(self, api_base: str, api_key: str, model: str) -> None:
        self.api_base = api_base
        self.api_key = api_key
        self.model = model

    def analyze(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        image_count = _count_images(messages)
        logger.info(
            "vlm_request model=%s endpoint=%s image_count=%s",
            self.model,
            self.api_base,
            image_count,
        )
        response = requests.post(
            self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=90,
        )
        logger.info("vlm_response status=%s", response.status_code)
        response.raise_for_status()
        payload = response.json()
        usage = payload.get("usage", {})
        if usage:
            logger.info(
                "vlm_usage prompt_tokens=%s completion_tokens=%s total_tokens=%s image_tokens=%s",
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
                usage.get("total_tokens"),
                usage.get("prompt_tokens_details", {}).get("image_tokens"),
            )
        content = payload["choices"][0]["message"]["content"]
        logger.info("vlm_raw_content=%s", _preview(content, 2000))
        parsed = json.loads(content)
        logger.info(
            "vlm_parsed_summary shot_id=%s shot_type=%s keys=%s",
            parsed.get("shot_id"),
            parsed.get("shot_type"),
            ",".join(sorted(parsed.keys())),
        )
        return parsed


def _count_images(messages: list[dict[str, Any]]) -> int:
    count = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            count += sum(1 for item in content if item.get("type") == "image_url")
    return count


def _preview(value: str, limit: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit] + "...[truncated]"
