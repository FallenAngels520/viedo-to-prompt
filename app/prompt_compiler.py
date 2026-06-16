from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from typing import Any

from app.logging_config import logger
from app.models import NewContentInput, ShotGrammar


class PromptCompiler:
    def compile_replicate_with_llm(
        self,
        grammars: list[ShotGrammar],
        client: Any,
        aspect_ratio: str = "16:9",
        video_model: str = "Seedance 2.0",
        max_workers: int = 4,
    ) -> dict[str, object]:
        total = len(grammars)
        worker_count = max(1, min(max_workers, total or 1))
        logger.info(
            "replicate_llm_parallel_start total=%s max_workers=%s",
            total,
            worker_count,
        )
        generated_by_index: dict[int, dict[str, object]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    self._compile_replicate_llm_one,
                    index,
                    grammar,
                    total,
                    client,
                    aspect_ratio,
                    video_model,
                ): index
                for index, grammar in enumerate(grammars, start=1)
            }
            for future in as_completed(futures):
                index, item = future.result()
                generated_by_index[index] = item
        generated = [generated_by_index[index] for index in sorted(generated_by_index)]
        return {
            "mode": "replicate_llm",
            "global_style_prompt": "Seedance 2.0 大模型原片复刻提示词",
            "video_model": video_model,
            "generated_prompts": generated,
        }

    def compile_replicate(
        self,
        grammars: list[ShotGrammar],
        aspect_ratio: str = "16:9",
        video_model: str = "Seedance 2.0",
    ) -> dict[str, object]:
        generated = []
        for index, grammar in enumerate(grammars, start=1):
            prompt = self._compile_replicate_one(index, grammar, aspect_ratio, video_model)
            generated.append(
                {
                    "shot_id": grammar.shot_id,
                    "duration": f"{grammar.time_range['duration']:g}s",
                    "prompt": prompt,
                    "seedance_prompt": prompt,
                    "negative_prompt": self._replicate_negative_prompt(grammar),
                    "source_visual_notes": {
                        "shot_type": grammar.shot_type,
                        "camera": grammar.camera,
                        "composition": grammar.composition,
                        "action_pattern": grammar.action_pattern,
                        "emotion_pattern": grammar.emotion_pattern,
                        "editing_function": grammar.editing_function,
                        "continuity_rule": grammar.continuity_rule,
                    },
                }
            )
        return {
            "mode": "replicate",
            "global_style_prompt": "Seedance 2.0 原片复刻提示词",
            "video_model": video_model,
            "generated_prompts": generated,
        }

    def compile(
        self, grammars: list[ShotGrammar], new_content: NewContentInput
    ) -> dict[str, object]:
        generated = []
        for index, grammar in enumerate(grammars, start=1):
            prompt = self._compile_one(index, grammar, new_content)
            generated.append(
                {
                    "shot_id": grammar.shot_id,
                    "duration": f"{grammar.time_range['duration']:g}s",
                    "prompt": prompt,
                    "negative_prompt": (
                        "不要切换场景，不要改变人物站位，不要让人物突然变脸，"
                        "不要让动作过快，不要加入无关角色，不要改变镜头节奏。"
                    ),
                }
            )
        return {
            "global_style_prompt": new_content.target_style,
            "video_model": new_content.video_model,
            "generated_prompts": generated,
        }

    def _compile_one(
        self, index: int, grammar: ShotGrammar, new_content: NewContentInput
    ) -> str:
        return (
            f"Shot {index:02d}，时长{grammar.time_range['duration']:g}秒，"
            f"{new_content.aspect_ratio}。{new_content.location}。"
            f"{new_content.character_a}作为 Character A，{new_content.character_b}作为 Character B。"
            f"故事语境：{new_content.new_story}。"
            f"镜头结构：{grammar.camera['shot_size_start']}到{grammar.camera['shot_size_end']}，"
            f"{grammar.camera['angle']}，{grammar.camera['movement']}，"
            f"节奏{grammar.camera['camera_energy']}。"
            f"构图保持{grammar.composition['main_subject_position']}与"
            f"{grammar.composition['secondary_subject_position']}的空间关系。"
            f"动作节奏：{grammar.action_pattern['start']}，"
            f"{grammar.action_pattern['middle']}，{grammar.action_pattern['end']}。"
            f"情绪推进：{grammar.emotion_pattern['start']}，"
            f"{grammar.emotion_pattern['middle']}，{grammar.emotion_pattern['end']}。"
            f"剪辑功能：{grammar.editing_function}。"
            f"保持原镜头语法，不复刻原视频人物、场景或台词。"
        )

    def _compile_replicate_one(
        self,
        index: int,
        grammar: ShotGrammar,
        aspect_ratio: str,
        video_model: str,
    ) -> str:
        duration = grammar.time_range["duration"]
        camera = _mapping_sentence(grammar.camera)
        composition = _mapping_sentence(grammar.composition)
        action = _mapping_sentence(grammar.action_pattern)
        emotion = _mapping_sentence(grammar.emotion_pattern)
        return (
            f"{video_model}，Shot {index:02d}，{aspect_ratio}，时长 {duration:g} 秒。"
            f"复刻原视频这一镜头的画面和拍法：镜头类型为 {grammar.shot_type}。"
            f"镜头语言：{camera}。"
            f"画面构图与视觉主体：{composition}。"
            f"动作过程：{action}。"
            f"情绪氛围：{emotion}。"
            f"剪辑功能：{grammar.editing_function}。"
            f"连续性要求：{grammar.continuity_rule}。"
            f"参考镜头描述：{grammar.prompt_pattern}。"
            "保持同样的主体关系、空间层次、运动节奏、光影气氛和镜头能量，"
            "生成电影感、高细节、稳定连贯的视频画面。"
        )

    def _replicate_negative_prompt(self, grammar: ShotGrammar) -> str:
        return (
            "不要改变镜头景别，不要改变机位角度，不要改变主要构图关系，"
            "不要移除原镜头中的核心视觉主体，不要加入无关角色或无关物体，"
            "不要切换到其他场景，不要让镜头运动过快，不要破坏原有动作节奏，"
            "不要改变情绪氛围，不要让人物、物体或背景突然变形，"
            f"不要违背连续性要求：{grammar.continuity_rule}。"
        )

    def _compile_replicate_llm_one(
        self,
        index: int,
        grammar: ShotGrammar,
        total: int,
        client: Any,
        aspect_ratio: str,
        video_model: str,
    ) -> tuple[int, dict[str, object]]:
        logger.info(
            "replicate_llm_request shot_id=%s index=%s total=%s",
            grammar.shot_id,
            index,
            total,
        )
        fallback_prompt = self._compile_replicate_one(
            index, grammar, aspect_ratio, video_model
        )
        try:
            parsed = client.analyze(
                self._replicate_llm_messages(
                    index=index,
                    grammar=grammar,
                    aspect_ratio=aspect_ratio,
                    video_model=video_model,
                )
            )
            prompt = parsed.get("seedance_prompt") or parsed.get("prompt")
            negative_prompt = parsed.get("negative_prompt")
            source_reasoning = parsed.get("source_reasoning", "")
            if not prompt or not negative_prompt:
                raise ValueError("LLM response missing prompt fields")
            logger.info(
                "replicate_llm_response shot_id=%s prompt_chars=%s negative_chars=%s",
                grammar.shot_id,
                len(prompt),
                len(negative_prompt),
            )
        except Exception as exc:
            logger.warning(
                "replicate_llm_failed fallback=rule shot_id=%s error=%s",
                grammar.shot_id,
                exc,
            )
            prompt = fallback_prompt
            negative_prompt = self._replicate_negative_prompt(grammar)
            source_reasoning = "LLM 生成失败，已回退到规则版复刻提示词。"

        return index, {
            "shot_id": grammar.shot_id,
            "duration": f"{grammar.time_range['duration']:g}s",
            "prompt": prompt,
            "seedance_prompt": prompt,
            "negative_prompt": negative_prompt,
            "source_reasoning": source_reasoning,
            "source_visual_notes": {
                "shot_type": grammar.shot_type,
                "camera": grammar.camera,
                "composition": grammar.composition,
                "action_pattern": grammar.action_pattern,
                "emotion_pattern": grammar.emotion_pattern,
                "editing_function": grammar.editing_function,
                "continuity_rule": grammar.continuity_rule,
            },
        }

    def _replicate_llm_messages(
        self,
        index: int,
        grammar: ShotGrammar,
        aspect_ratio: str,
        video_model: str,
    ) -> list[dict[str, str]]:
        payload = {
            "shot_index": index,
            "target_model": video_model,
            "aspect_ratio": aspect_ratio,
            "shot_grammar": grammar.to_dict(),
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是 AI 视频生成提示词导演，专门把镜头语法 JSON 改写成 Seedance 2.0 可用的中文视频提示词。"
                    "当前任务只做原视频复刻，不做新角色、新场景、新剧情迁移。"
                    "必须保留原镜头里的具体视觉主体、环境、构图、机位、运镜、动作节奏、情绪氛围和剪辑功能。"
                    "不要机械罗列字段，要写成自然、可执行、适合视频生成模型理解的一段中文提示词。"
                    "只输出 JSON，不要输出 Markdown。"
                ),
            },
            {
                "role": "user",
                "content": (
                    "请根据下面的 shot grammar 生成一条 Seedance 2.0 原视频复刻提示词。"
                    "JSON 输出格式必须是："
                    '{"seedance_prompt":"...","negative_prompt":"...","source_reasoning":"..."}'
                    "。shot grammar 如下：\n"
                    f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                ),
            },
        ]


def _mapping_sentence(values: dict[str, str]) -> str:
    parts = [f"{key}: {value}" for key, value in values.items() if value]
    return "；".join(parts) if parts else "保持原镜头视觉特征"
