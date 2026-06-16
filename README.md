# Video-to-Shot-Grammar Prompt System

本项目实现 `design.md` 中的本地 MVP：上传 AI 漫剧视频，拆分镜头，抽取关键帧，生成 Shot Grammar JSON，并把新角色、新场景、新剧情编译成每个镜头的视频生成提示词。

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

## 视频工具

后端优先从环境变量读取：

```powershell
$env:FFMPEG_PATH="C:\path\to\ffmpeg.exe"
$env:FFPROBE_PATH="C:\path\to\ffprobe.exe"
```

如果未配置，会尝试使用 PATH 中的 `ffmpeg` / `ffprobe`，并在当前机器上自动探测 Remotion 自带的二进制路径。

## VLM 配置

默认情况下，系统使用本地确定性分析器生成稳定的 Shot Grammar JSON，方便无模型密钥时跑通 MVP。

如需调用真实 VLM，配置 OpenAI-compatible chat completions 接口：

```powershell
$env:VLM_API_BASE="https://your-provider.example/v1/chat/completions"
$env:VLM_API_KEY="your-api-key"
$env:VLM_MODEL="your-vision-model"
```

配置完整时，后端会把每个镜头的 `frame_start.jpg`、`frame_mid.jpg`、`frame_end.jpg` 作为 base64 图片发送给 VLM，并要求模型只输出可迁移的 Shot Grammar JSON。

## MVP 说明

- VLM 第一版支持真实 OpenAI-compatible VLM；未配置密钥时自动回退到本地确定性分析器，输出稳定 Shot Grammar 字段，保证端到端流程可运行。
- 镜头检测使用 ffmpeg scene detection；如果未检测到有效切点或工具不可用，回退为默认每 3 秒一个镜头。
- 本版本不自动生成最终视频，不做原视频逐帧复刻，不保存商业账号信息。
"# viedo-to-prompt" 
