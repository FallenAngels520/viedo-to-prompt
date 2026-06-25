# Video-to-Shot-Grammar Prompt System

本项目用于把 AI 漫剧视频拆解成可复用的镜头语言结构，并生成 Seedance 2.0 复刻提示词。当前实现重点不是单次让 VLM 描述视频，而是把视频拆解、边界校验、镜头语言抽象、提示词生成做成可检查、可恢复、可扩展的 Loop Engineering 流程。

## 当前能力

- 上传 MP4 视频并读取基础信息。
- 使用 PySceneDetect / ffmpeg / OpenCV 生成候选镜头切点。
- 抽取每个镜头的 `frame_start.jpg`、`frame_mid.jpg`、`frame_end.jpg`。
- 使用 VLM 校验候选镜头是否需要拆分或合并；未配置 VLM 时使用确定性 fallback。
- 输出 `Scene -> Shot -> Frame` 结构、`Shot Grammar JSON` 和 Seedance 复刻提示词。
- 写入 `analysis.json`、`shot_list.json`、`replication_state.json`、`replicate_prompts.json` 等中间产物。

当前不做 OCR / Whisper 识别，只保留 `context_tracks.speech` 和 `context_tracks.ocr` 扩展点。

## Loop Engineering 结构

项目现在以 `ReplicationHarness` 作为执行层，围绕状态文件推进 loop：

```text
ReplicationHarness
  -> AnalysisPipeline
  -> ReplicationStateStore
  -> replication_state.json
```

已落地的 loop：

1. `shot_detection_loop`
   - 输入原视频。
   - 生成候选镜头、修正后的最终镜头、场景、关键帧。
   - 输出 `shot_list.json` 和 `analysis.json`。

2. `shot_language_loop`
   - 检查每个 `shot_grammar` 是否缺少关键字段。
   - 写入 `analysis_quality`、`missing_grammar_fields`、`needs_review`。

3. `prompt_generation_loop`
   - 生成并保存 `replicate_prompts.json`。
   - 更新下一步为 `review_generated_prompts`。

状态文件 `replication_state.json` 记录：

- `project_id`
- `source_video`
- `current_stage`
- `next_action`
- `candidate_shots`
- `scenes`
- `shots`
- `context_tracks`
- `errors`
- `artifacts`
- `loops`

## 运行

```powershell
E:\conda\python.exe -m uvicorn app.server:app --reload --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

## 测试

```powershell
E:\conda\python.exe -m pytest -q
```

## 视频工具配置

后端优先从环境变量读取：

```powershell
$env:FFMPEG_PATH="C:\path\to\ffmpeg.exe"
$env:FFPROBE_PATH="C:\path\to\ffprobe.exe"
```

如果未配置，会尝试使用 PATH 中的 `ffmpeg` / `ffprobe`，并尝试自动发现本机 Remotion 自带的二进制路径。

PySceneDetect 是可选增强依赖；不可用时会自动回落到 ffmpeg scene detection，再回落到 OpenCV / 固定时长切分。

## VLM 配置

未配置 VLM 时，系统使用本地确定性分析器生成稳定的 Shot Grammar，保证 MVP 可以端到端运行。

如需调用真实 VLM，配置 OpenAI-compatible chat completions 接口：

```powershell
$env:VLM_API_BASE="https://your-provider.example/v1/chat/completions"
$env:VLM_API_KEY="your-api-key"
$env:VLM_MODEL="your-vision-model"
```

配置完整后，后端会把每个镜头的关键帧作为 base64 图片发送给 VLM，用于边界校验和镜头语言分析。

## 主要输出

分析完成后，视频目录下会生成：

```text
data/videos/<video_id>/
  source.mp4
  analysis.json
  analysis.partial.json
  shot_list.json
  replication_state.json
  replicate_prompts.json
  shots/
    S01/
      frame_start.jpg
      frame_mid.jpg
      frame_end.jpg
      meta.json
      shot_grammar.json
```

其中 `replication_state.json` 是 harness/loop 的核心状态文件，后续人工检查、返工、继续执行都应基于它。

## MVP 边界

- 不自动生成最终视频。
- 不自动调用 Seedance API。
- 不做 OCR / Whisper 识别。
- 不逐帧复刻原视频人物、场景和商业素材。
- 当前目标是稳定输出可检查、可复用、可继续迭代的镜头结构和 Seedance prompt。
