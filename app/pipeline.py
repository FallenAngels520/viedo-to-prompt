from __future__ import annotations

from pathlib import Path
from typing import Callable, Any

from app.config import load_config
from app.grammar import ShotGrammarAnalyzer, VLMShotGrammarAnalyzer, VideoStructureSummarizer
from app.keyframes import KeyframeService
from app.logging_config import logger
from app.shot_detection import ShotDetectionService
from app.vlm_client import OpenAICompatibleVLMClient
from app.video_info import VideoInfoService


class AnalysisPipeline:
    def __init__(
        self,
        info_service: VideoInfoService | None = None,
        shot_service: ShotDetectionService | None = None,
        keyframe_service: KeyframeService | None = None,
        grammar_analyzer: ShotGrammarAnalyzer | None = None,
        summarizer: VideoStructureSummarizer | None = None,
    ) -> None:
        config = load_config()
        self.info_service = info_service or VideoInfoService(config.ffprobe_path)
        self.shot_service = shot_service or ShotDetectionService(config.ffmpeg_path)
        self.keyframe_service = keyframe_service or KeyframeService(config.ffmpeg_path)
        self.grammar_analyzer = grammar_analyzer or _default_grammar_analyzer(config)
        self.summarizer = summarizer or VideoStructureSummarizer()

    def analyze(
        self,
        video_path: Path,
        shots_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        partial_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, object]:
        def report(
            stage: str,
            message: str,
            progress: int,
            current: int = 0,
            total: int = 0,
        ) -> None:
            logger.info(
                "analysis_progress stage=%s progress=%s current=%s total=%s message=%s",
                stage,
                progress,
                current,
                total,
                message,
            )
            if progress_callback:
                progress_callback(
                    {
                        "stage": stage,
                        "message": message,
                        "progress": progress,
                        "current": current,
                        "total": total,
                    }
                )

        report("video_info", "正在读取视频基础信息", 5)
        video_info = self.info_service.probe(video_path)
        report("shot_detection", "正在自动拆分镜头", 15)
        shots = self.shot_service.detect(video_path, video_info.duration)
        total = len(shots)
        keyframes = []
        for index, shot in enumerate(shots, start=1):
            report(
                "keyframes",
                f"正在抽取关键帧 {index}/{total}",
                _scaled_progress(index, total, 15, 45),
                index,
                total,
            )
            keyframes.append(self.keyframe_service.extract(video_path, shots_dir, shot))

        grammars = []
        for index, (shot, frames) in enumerate(zip(shots, keyframes), start=1):
            report(
                "vlm",
                f"正在调用 VLM 分析镜头 {index}/{total}",
                _scaled_progress(index, total, 45, 92),
                index,
                total,
            )
            grammar = self.grammar_analyzer.analyze(shot, frames)
            grammars.append(grammar)
            if partial_callback:
                partial_callback(
                    {
                        "status": "partial",
                        "video_info": video_info.to_dict(),
                        "shots": [item.to_dict() for item in shots],
                        "keyframes": [item.to_dict() for item in keyframes],
                        "shot": shot.to_dict(),
                        "grammar": grammar.to_dict(),
                        "shot_grammar": [item.to_dict() for item in grammars],
                    }
                )

        report("summary", "正在生成全局镜头结构总结", 96)
        video_structure = self.summarizer.summarize(grammars)
        report("completed", "分析完成", 100, total, total)
        return {
            "video_info": video_info.to_dict(),
            "shots": [shot.to_dict() for shot in shots],
            "keyframes": [frames.to_dict() for frames in keyframes],
            "shot_grammar": [grammar.to_dict() for grammar in grammars],
            "video_structure": video_structure,
        }


def _default_grammar_analyzer(config):
    if config.vlm_api_base and config.vlm_api_key and config.vlm_model:
        return VLMShotGrammarAnalyzer(
            OpenAICompatibleVLMClient(
                api_base=config.vlm_api_base,
                api_key=config.vlm_api_key,
                model=config.vlm_model,
            )
        )
    return ShotGrammarAnalyzer()


def _scaled_progress(current: int, total: int, start: int, end: int) -> int:
    if total <= 0:
        return end
    return min(end, round(start + ((end - start) * current / total)))
