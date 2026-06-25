from app.shot_language_loop import ShotLanguageLoopEvaluator


def test_shot_language_evaluator_marks_complete_grammar_verified():
    evaluator = ShotLanguageLoopEvaluator()

    result = evaluator.evaluate(
        [
            {
                "shot_id": "S01",
                "time_range": {"start": 0, "end": 2, "duration": 2},
                "shot_type": "close-up",
                "camera": {"movement": "slow push-in"},
                "composition": {"main_subject_position": "center"},
                "action_pattern": {"start": "pause"},
                "emotion_pattern": {"start": "tense"},
                "editing_function": "reveal emotion",
                "continuity_rule": "keep tension",
                "prompt_pattern": "slow close-up",
            }
        ]
    )

    assert result["items"][0]["shot_id"] == "S01"
    assert result["items"][0]["status"] == "verified"
    assert result["items"][0]["missing_fields"] == []
    assert result["items"][0]["analysis_quality"] == 1.0
    assert result["summary"]["needs_review_count"] == 0


def test_shot_language_evaluator_marks_incomplete_grammar_for_review():
    evaluator = ShotLanguageLoopEvaluator()

    result = evaluator.evaluate(
        [
            {
                "shot_id": "S01",
                "time_range": {"start": 0, "end": 2, "duration": 2},
                "shot_type": "",
                "camera": {},
                "composition": {},
            }
        ]
    )

    item = result["items"][0]
    assert item["status"] == "needs_review"
    assert "action_pattern" in item["missing_fields"]
    assert "prompt_pattern" in item["missing_fields"]
    assert item["analysis_quality"] < 1.0
    assert result["summary"]["needs_review_count"] == 1
