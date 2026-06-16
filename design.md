# AI 漫剧镜头语法提取器 MVP 需求文档

## 1. 项目名称

AI 漫剧镜头语法提取器
Video-to-Shot-Grammar Prompt System

## 2. 项目目标

本项目不是为了一比一复刻原视频的人物、场景、台词或具体剧情，而是从原视频中提取可复用的“镜头语法”。

所谓“镜头语法”包括：

* 镜头景别
* 镜头角度
* 运镜方式
* 画面构图
* 人物站位关系
* 主体动作节奏
* 情绪推进方式
* 剪辑节奏
* 镜头之间的承接关系
* 该镜头在剧情中的功能

系统需要支持用户上传一个 AI 漫剧视频，自动分析视频的镜头结构，并输出一套可替换人物、场景、剧情的镜头模板。用户可以输入新的角色、场景和剧情设定，系统根据提取出的镜头模板生成新的 AI 视频生成提示词。

最终目标是实现：

原视频内容 A + 镜头结构 X
转换为：
新视频内容 B + 镜头结构 X

即：不复刻内容，只复刻拍法。

## 3. MVP 范围

MVP 只实现以下功能：

1. 上传一个本地视频文件
2. 获取视频基础信息
3. 自动拆分镜头
4. 每个镜头抽取关键帧
5. 使用 VLM 分析每个镜头的镜头语法
6. 输出结构化 Shot Grammar JSON
7. 用户输入新角色、新场景、新剧情
8. 系统根据 Shot Grammar 生成新视频提示词

MVP 暂不实现：

* 自动生成视频
* 自动对比生成视频和原视频
* 自动调参
* 多模型批量生成
* 在线素材库
* 商业化账号系统
* 复杂剪辑器

## 4. 用户流程

### 4.1 上传原视频

用户上传一个 AI 漫剧视频。

限制：

* 支持 mp4
* 建议时长 5 秒到 60 秒
* 支持 9:16、16:9、1:1
* 文件大小第一版可限制在 200MB 以内

系统读取视频信息：

* 视频时长
* 分辨率
* 宽高比
* fps
* 音频是否存在

### 4.2 自动拆镜头

系统对视频进行 shot detection。

输出每个镜头的时间范围：

```json
[
  {
    "shot_id": "S01",
    "start_time": 0.0,
    "end_time": 2.4,
    "duration": 2.4
  },
  {
    "shot_id": "S02",
    "start_time": 2.4,
    "end_time": 5.8,
    "duration": 3.4
  }
]
```

如果自动拆分失败，则退化为按固定时间切分，例如每 3 秒切一个镜头。

### 4.3 抽取关键帧

每个镜头至少抽 3 张关键帧：

* 起始帧
* 中间帧
* 结束帧

如果后续扩展，可增加：

* 动作变化最大帧
* 表情最明显帧
* 构图最稳定帧

每个镜头的关键帧保存到本地目录：

```text
/data/videos/{video_id}/shots/S01/frame_start.jpg
/data/videos/{video_id}/shots/S01/frame_mid.jpg
/data/videos/{video_id}/shots/S01/frame_end.jpg
```

### 4.4 VLM 镜头语法分析

系统将每个镜头的关键帧发送给 VLM。

VLM 的任务不是描述具体人物和场景，而是提取镜头结构。

VLM 必须输出 JSON。

字段如下：

```json
{
  "shot_id": "S01",
  "time_range": {
    "start": 0.0,
    "end": 2.4,
    "duration": 2.4
  },
  "shot_type": "emotional confrontation opening",
  "camera": {
    "shot_size_start": "medium shot",
    "shot_size_end": "close-up",
    "angle": "eye-level",
    "movement": "slow push-in",
    "camera_energy": "slow and tense"
  },
  "composition": {
    "main_subject_position": "foreground right",
    "secondary_subject_position": "background left",
    "spatial_relationship": "two characters separated by emotional distance",
    "depth_structure": "foreground character dominates, background character creates tension"
  },
  "action_pattern": {
    "start": "Character A remains still with head slightly lowered",
    "middle": "Character A slowly raises eyes or shifts gaze",
    "end": "Character B pauses before reacting"
  },
  "emotion_pattern": {
    "start": "suppressed emotion",
    "middle": "tension increases",
    "end": "unresolved emotional pressure"
  },
  "editing_function": "establish conflict and create suspense",
  "continuity_rule": "next shot should maintain the same emotional tension and spatial relationship",
  "replaceable_variables": {
    "character_a": "any questioning, vulnerable or emotionally pressured character",
    "character_b": "any evasive, powerful or silent character",
    "location": "any tense enclosed or semi-enclosed space",
    "prop": "optional object that can show emotional pressure"
  },
  "prompt_pattern": "Use a medium shot that slowly pushes into Character A. Keep Character A in the foreground and Character B in the background. Character A remains still, then slowly raises their eyes. Character B delays their reaction. Maintain emotional tension and spatial distance."
}
```

### 4.5 全局镜头结构总结

系统需要在分析完全部镜头后，生成一个全局总结。

输出：

```json
{
  "video_structure": {
    "total_shots": 8,
    "average_shot_duration": 2.7,
    "editing_rhythm": "slow emotional build-up with occasional close-up inserts",
    "camera_style": "stable cinematic camera with slow push-ins and reaction shots",
    "dominant_shot_types": [
      "confrontation opening",
      "reaction close-up",
      "detail insert",
      "emotional pause",
      "turning point shot"
    ],
    "emotional_curve": "suppression -> tension -> reaction -> escalation -> hook ending"
  }
}
```

### 4.6 用户输入新内容

用户可以输入：

```json
{
  "target_style": "AI 漫剧，半写实 3D，短剧感",
  "new_story": "女赏金猎人在雨夜质问机械改造男性为什么背叛她",
  "character_a": "年轻女赏金猎人，黑色短发，皮衣，手握破损身份牌",
  "character_b": "机械改造男性，高大沉默，半张脸是金属结构",
  "location": "赛博朋克雨夜巷道，霓虹灯，积水地面",
  "aspect_ratio": "9:16",
  "video_model": "Seedance"
}
```

### 4.7 生成新视频提示词

系统将原视频提取出的 Shot Grammar 和用户输入的新内容结合，生成每个镜头的视频提示词。

输出格式：

```json
{
  "generated_prompts": [
    {
      "shot_id": "S01",
      "duration": "3s",
      "prompt": "Shot 01，时长3秒，9:16。赛博朋克雨夜巷道，年轻女赏金猎人站在画面右前景，机械改造男性站在画面左后景并背对她。镜头从中景缓慢推近到女赏金猎人的脸部。她低头停顿，然后缓慢抬眼，压住情绪质问。机械改造男性没有立刻回应，短暂停顿后缓慢转头。保持人物空间距离，保持压迫式对峙结构，镜头不要快速移动，不要改变站位。",
      "negative_prompt": "不要切换场景，不要改变人物站位，不要让人物突然变脸，不要让动作过快，不要加入无关角色，不要改变镜头节奏。"
    }
  ]
}
```

## 5. 核心模块

### 5.1 VideoUploadService

职责：

* 接收视频上传
* 保存视频文件
* 生成 video_id
* 记录元数据

### 5.2 VideoInfoService

职责：

* 调用 ffprobe 获取视频信息
* 输出 duration、fps、width、height、aspect_ratio

### 5.3 ShotDetectionService

职责：

* 使用 shot detection 工具拆分镜头
* 输出 shot list
* 支持失败回退策略

失败回退：

* 如果检测不到镜头切换，则按固定时间间隔切分
* 默认 3 秒一个片段

### 5.4 KeyframeService

职责：

* 根据 shot list 抽关键帧
* 每个镜头抽 start、middle、end 三帧
* 保存图片路径

### 5.5 ShotGrammarAnalyzer

职责：

* 调用 VLM
* 输入每个镜头关键帧
* 输出 Shot Grammar JSON
* 保证 JSON 字段稳定

### 5.6 VideoStructureSummarizer

职责：

* 汇总所有镜头 JSON
* 生成全局视频结构
* 提取整体剪辑节奏和情绪曲线

### 5.7 PromptCompiler

职责：

* 输入 Shot Grammar
* 输入用户的新角色、新场景、新剧情
* 输出每个镜头的视频生成 prompt
* 支持不同视频模型的提示词格式

第一版优先支持：

* 通用中文版 prompt
* Seedance 版本 prompt

后续扩展：

* Kling 版本
* Runway 版本
* Veo 版本
* Sora 版本

## 6. 页面设计

### 页面 1：上传页

功能：

* 上传视频
* 显示视频基础信息
* 点击“开始分析”

### 页面 2：镜头分析页

显示：

* 原视频播放器
* 镜头列表
* 每个镜头的起止时间
* 每个镜头的关键帧
* 每个镜头的 Shot Grammar JSON

### 页面 3：新内容输入页

用户填写：

* 新故事
* 角色 A
* 角色 B
* 场景
* 目标风格
* 视频比例
* 目标视频模型

### 页面 4：Prompt 输出页

显示：

* 全局风格 prompt
* 每个镜头 prompt
* 每个镜头 negative prompt
* 一键复制
* 导出 JSON
* 导出 Markdown

## 7. 验收标准

MVP 完成后，应满足以下标准：

1. 用户可以上传一个 mp4 视频
2. 系统可以读取视频基础信息
3. 系统可以自动拆分镜头
4. 系统可以为每个镜头抽取至少 3 张关键帧
5. 系统可以输出每个镜头的 Shot Grammar JSON
6. Shot Grammar 中不应过度绑定原视频的人物和场景
7. 系统可以根据新角色、新场景、新剧情生成新 prompt
8. 生成的 prompt 应保留原视频的镜头结构、动作节奏、情绪推进和剪辑功能
9. 输出结果可以复制给 AI 视频生成模型使用

## 8. 非目标

本项目第一版不追求：

* 逐帧复刻
* 原角色一致性
* 原场景一致性
* 原台词一致性
* 原视频版权内容复刻
* 自动生成最终视频
* 完全无人干预

本项目第一版只追求：

* 提取镜头拍法
* 提取视频节奏
* 提取动作与情绪结构
* 生成可迁移的新视频提示词

## 9. 一句话总结

本系统的目标是：

从爆款 AI 漫剧视频中提取“拍法”，而不是复制“内容”。

最终实现：

原视频的镜头结构
+
用户的新人物、新场景、新剧情
==============

一套可用于生成同款镜头感觉的新 AI 视频提示词。
