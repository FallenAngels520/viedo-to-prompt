from __future__ import annotations

from typing import Any


class ShotLanguageLoopEvaluator:
    required_fields = [
        "shot_id",
        "time_range",
        "shot_type",
        "camera",
        "composition",
        "action_pattern",
        "emotion_pattern",
        "editing_function",
        "continuity_rule",
        "prompt_pattern",
    ]

    def evaluate(self, grammars: list[dict[str, Any]]) -> dict[str, Any]:
        items = [self._evaluate_one(grammar) for grammar in grammars]
        needs_review_count = sum(1 for item in items if item["status"] == "needs_review")
        return {
            "items": items,
            "summary": {
                "grammar_count": len(grammars),
                "verified_count": len(items) - needs_review_count,
                "needs_review_count": needs_review_count,
            },
        }

    def _evaluate_one(self, grammar: dict[str, Any]) -> dict[str, Any]:
        missing = [
            field for field in self.required_fields if not self._has_value(grammar.get(field))
        ]
        present_count = len(self.required_fields) - len(missing)
        quality = round(present_count / len(self.required_fields), 3)
        return {
            "shot_id": grammar.get("shot_id", ""),
            "status": "verified" if not missing else "needs_review",
            "analysis_quality": quality,
            "missing_fields": missing,
        }

    def _has_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict | list):
            return bool(value)
        return True
