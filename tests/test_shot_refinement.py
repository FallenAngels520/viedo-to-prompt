from pathlib import Path

from app.keyframes import KeyframeService
from app.models import Keyframes, Shot
from app.shot_refinement import (
    CandidateShotDecision,
    ShotBoundaryRefiner,
    TransitionDecision,
    VLMShotBoundaryValidator,
)


class FakeKeyframeService:
    def extract(self, video_path: Path, shots_dir: Path, shot: Shot) -> Keyframes:
        shot_dir = shots_dir / shot.shot_id
        shot_dir.mkdir(parents=True, exist_ok=True)
        for name in ["frame_start.jpg", "frame_mid.jpg", "frame_end.jpg"]:
            (shot_dir / name).write_bytes(b"jpg")
        return KeyframeService("ffmpeg").plan_keyframes(shots_dir, shot)


class KeepAllValidator:
    def validate_candidate(self, shot: Shot, keyframes: Keyframes) -> CandidateShotDecision:
        return CandidateShotDecision()

    def validate_transition(
        self,
        previous_shot: Shot,
        previous_keyframes: Keyframes,
        current_shot: Shot,
        current_keyframes: Keyframes,
    ) -> TransitionDecision:
        return TransitionDecision(is_true_cut=True)


def test_refiner_filters_too_short_transition_candidates(tmp_path):
    refiner = ShotBoundaryRefiner(
        validator=KeepAllValidator(),
        keyframe_service=FakeKeyframeService(),
        min_duration_seconds=0.3,
    )
    shots = [
        Shot("S01", 0.0, 0.2, 0.2),
        Shot("S02", 0.2, 2.0, 1.8),
        Shot("S03", 2.0, 4.0, 2.0),
    ]

    refined = refiner.refine(Path("source.mp4"), tmp_path, shots)

    assert refined == [
        Shot("S01", 0.2, 2.0, 1.8),
        Shot("S02", 2.0, 4.0, 2.0),
    ]


def test_refiner_merges_adjacent_candidates_when_validator_rejects_cut(tmp_path):
    class MergeFirstCutValidator(KeepAllValidator):
        def validate_transition(
            self,
            previous_shot: Shot,
            previous_keyframes: Keyframes,
            current_shot: Shot,
            current_keyframes: Keyframes,
        ) -> TransitionDecision:
            if previous_shot.shot_id == "S01" and current_shot.shot_id == "S02":
                return TransitionDecision(is_true_cut=False, reason="continuous push-in")
            return TransitionDecision(is_true_cut=True)

    refiner = ShotBoundaryRefiner(
        validator=MergeFirstCutValidator(),
        keyframe_service=FakeKeyframeService(),
    )
    shots = [
        Shot("S01", 0.0, 2.0, 2.0),
        Shot("S02", 2.0, 4.0, 2.0),
        Shot("S03", 4.0, 6.0, 2.0),
    ]

    refined = refiner.refine(Path("source.mp4"), tmp_path, shots)

    assert refined == [
        Shot("S01", 0.0, 4.0, 4.0),
        Shot("S02", 4.0, 6.0, 2.0),
    ]


def test_refiner_uses_merged_shot_end_frames_for_next_transition_check(tmp_path):
    class MergeThenInspectValidator(KeepAllValidator):
        def __init__(self):
            self.second_transition_end_timestamp = None

        def validate_transition(
            self,
            previous_shot: Shot,
            previous_keyframes: Keyframes,
            current_shot: Shot,
            current_keyframes: Keyframes,
        ) -> TransitionDecision:
            if previous_shot.shot_id == "S01" and current_shot.shot_id == "S02":
                return TransitionDecision(is_true_cut=False)
            if previous_shot.start_time == 0.0 and previous_shot.end_time == 4.0:
                self.second_transition_end_timestamp = previous_keyframes.timestamps["end"]
            return TransitionDecision(is_true_cut=True)

    validator = MergeThenInspectValidator()
    refiner = ShotBoundaryRefiner(
        validator=validator,
        keyframe_service=FakeKeyframeService(),
    )
    shots = [
        Shot("S01", 0.0, 2.0, 2.0),
        Shot("S02", 2.0, 4.0, 2.0),
        Shot("S03", 4.0, 6.0, 2.0),
    ]

    refiner.refine(Path("source.mp4"), tmp_path, shots)

    assert validator.second_transition_end_timestamp == 3.96


def test_refiner_splits_candidate_when_validator_finds_internal_cut(tmp_path):
    class SplitValidator(KeepAllValidator):
        def validate_candidate(self, shot: Shot, keyframes: Keyframes) -> CandidateShotDecision:
            if shot.shot_id == "S01":
                return CandidateShotDecision(
                    same_shot=False,
                    need_split=True,
                    possible_split="between middle frame and end frame",
                )
            return CandidateShotDecision()

    refiner = ShotBoundaryRefiner(
        validator=SplitValidator(),
        keyframe_service=FakeKeyframeService(),
    )
    shots = [Shot("S01", 0.0, 8.0, 8.0)]

    refined = refiner.refine(Path("source.mp4"), tmp_path, shots)

    assert refined == [
        Shot("S01", 0.0, 6.0, 6.0),
        Shot("S02", 6.0, 8.0, 2.0),
    ]


def test_vlm_validator_asks_whether_candidate_frames_are_one_shot(tmp_path):
    class FakeClient:
        def __init__(self):
            self.messages = None

        def analyze(self, messages):
            self.messages = messages
            return {
                "same_shot": False,
                "need_split": True,
                "possible_split": "between start frame and middle frame",
                "reason": "composition changes",
            }

    shot = Shot("S01", 0.0, 4.0, 4.0)
    keyframes = FakeKeyframeService().extract(Path("source.mp4"), tmp_path, shot)
    client = FakeClient()

    decision = VLMShotBoundaryValidator(client).validate_candidate(shot, keyframes)

    content = client.messages[1]["content"]
    image_items = [item for item in content if item["type"] == "image_url"]
    assert decision == CandidateShotDecision(
        same_shot=False,
        need_split=True,
        possible_split="between start frame and middle frame",
        reason="composition changes",
    )
    assert len(image_items) == 3
    assert "one continuous shot" in content[0]["text"]


def test_vlm_validator_asks_whether_adjacent_candidates_are_a_true_cut(tmp_path):
    class FakeClient:
        def __init__(self):
            self.messages = None

        def analyze(self, messages):
            self.messages = messages
            return {"is_true_cut": False, "reason": "same camera move"}

    previous = Shot("S01", 0.0, 2.0, 2.0)
    current = Shot("S02", 2.0, 4.0, 2.0)
    previous_frames = FakeKeyframeService().extract(Path("source.mp4"), tmp_path, previous)
    current_frames = FakeKeyframeService().extract(Path("source.mp4"), tmp_path, current)
    client = FakeClient()

    decision = VLMShotBoundaryValidator(client).validate_transition(
        previous,
        previous_frames,
        current,
        current_frames,
    )

    content = client.messages[1]["content"]
    image_items = [item for item in content if item["type"] == "image_url"]
    assert decision == TransitionDecision(is_true_cut=False, reason="same camera move")
    assert len(image_items) == 2
    assert "true cut" in content[0]["text"]
