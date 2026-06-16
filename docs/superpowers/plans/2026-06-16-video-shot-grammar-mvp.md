# Video Shot Grammar MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Web MVP that turns an uploaded AI comic video into reusable Shot Grammar JSON and new video prompts.

**Architecture:** A FastAPI backend owns upload, video probing, shot segmentation, keyframe extraction, grammar analysis, structure summary, and prompt compilation. A static HTML frontend provides the four screens from `design.md`: upload, analysis, new content input, and prompt output. The first VLM implementation is a deterministic local analyzer behind a replaceable interface so the pipeline works without an external model key.

**Tech Stack:** Python 3.10, FastAPI, pytest, ffmpeg/ffprobe subprocess integration, vanilla HTML/CSS/JavaScript.

---

## File Structure

- Create `pyproject.toml`: pytest config and package metadata.
- Create `README.md`: local setup, ffmpeg path configuration, run/test commands, MVP limitations.
- Create `app/__init__.py`: package marker.
- Create `app/config.py`: storage paths and ffmpeg/ffprobe binary discovery.
- Create `app/models.py`: dataclasses for video info, shots, keyframes, grammar, prompts.
- Create `app/storage.py`: video id generation and workspace layout.
- Create `app/video_info.py`: `ffprobe` adapter.
- Create `app/shot_detection.py`: ffmpeg scene-detection adapter plus fixed-interval fallback.
- Create `app/keyframes.py`: extracts start/mid/end frames through ffmpeg.
- Create `app/grammar.py`: deterministic Shot Grammar analyzer and global summarizer.
- Create `app/prompt_compiler.py`: maps Shot Grammar plus user input into prompts.
- Create `app/pipeline.py`: orchestrates the full analysis workflow.
- Create `app/server.py`: FastAPI routes and static frontend mounting.
- Create `app/static/index.html`: four-step local Web UI.
- Create tests in `tests/` for core behavior and API-light orchestration.

## Success Criteria

- Upload accepts one `.mp4` file and stores it under `data/videos/{video_id}`.
- Video metadata is read via `ffprobe` when available.
- Shot detection returns shot ranges and falls back to 3-second intervals when detection cannot produce useful cuts.
- Each shot has `frame_start.jpg`, `frame_mid.jpg`, and `frame_end.jpg` paths.
- Shot Grammar JSON uses stable fields from `design.md` and avoids binding to original characters or scenes.
- Global structure summary reports total shots, average duration, editing rhythm, camera style, dominant shot types, and emotional curve.
- User-provided story, characters, location, style, aspect ratio, and model compile into per-shot prompts and negative prompts.
- Static UI can run against the API and export/copy JSON/Markdown.
- Tests cover model shape, fallback segmentation, prompt compilation, and pipeline orchestration with fake video tools.

## Implementation Tasks

### Task 1: Project Skeleton and Models

- [ ] Write failing tests for model serialization and storage layout.
- [ ] Create package files and dataclasses.
- [ ] Verify tests pass.

### Task 2: Video Tool Adapters

- [ ] Write failing tests for ffprobe parsing and fixed-interval fallback.
- [ ] Implement binary discovery, ffprobe parsing, scene-detection parsing, and fallback segmentation.
- [ ] Verify tests pass.

### Task 3: Keyframes, Grammar, Summary, and Prompts

- [ ] Write failing tests for keyframe path planning, Shot Grammar shape, global summary, and prompt compilation.
- [ ] Implement the services with deterministic local behavior.
- [ ] Verify tests pass.

### Task 4: Pipeline and FastAPI

- [ ] Write failing tests for orchestration using fake service dependencies.
- [ ] Implement upload, analyze, retrieve result, compile prompt, and export routes.
- [ ] Verify tests pass.

### Task 5: Static Four-Step UI and Docs

- [ ] Add the upload, analysis, new content, and output screens in `app/static/index.html`.
- [ ] Add README instructions.
- [ ] Run full pytest.
- [ ] Start the local server if possible and report the URL.

