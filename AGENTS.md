# Repository Guidelines

## Project Structure & Module Organization

This repository is a local MVP for turning uploaded videos into shot grammar JSON and reusable video-generation prompts. Core Python code lives in `app/`: `server.py` exposes FastAPI, `pipeline.py` coordinates analysis, media modules wrap ffmpeg/ffprobe, and `grammar.py` plus `prompt_compiler.py` produce outputs. The browser UI is `app/static/index.html`. Tests live in `tests/` and cover services, API behavior, VLM integration, and static UI checks. Runtime/generated video artifacts are under `data/videos/`; avoid committing large outputs unless explicitly needed.

## Build, Test, and Development Commands

- `E:\conda\python.exe -m uvicorn app.server:app --reload --host 127.0.0.1 --port 8000` starts the local FastAPI server and static UI.
- `E:\conda\python.exe -m pytest -q` runs the full pytest suite configured by `pyproject.toml`.
- `python -m pytest tests/test_server.py -q` runs a focused API test file when iterating on endpoints.

The app expects `ffmpeg` and `ffprobe` on `PATH` or configured via `FFMPEG_PATH` and `FFPROBE_PATH`.

## Coding Style & Naming Conventions

Use Python 3.10-compatible code, type hints where they clarify data flow, and the dataclass-oriented model style in `app/models.py`. Keep modules small and service-focused: configuration in `config.py`, media subprocess handling in media modules, and API request/response handling in `server.py`. Use `snake_case` for functions, variables, and tests; use `PascalCase` for classes. Follow 4-space indentation and standard-library-first import grouping. No formatter or linter is configured, so match adjacent files.

## Testing Guidelines

Tests use `pytest` with `tests/` as the configured test root and `.` on `pythonpath`. Name new tests `test_*.py` and test functions `test_*`. Prefer focused unit tests for grammar, prompt compilation, storage, and media helpers, plus FastAPI `TestClient` coverage for endpoint changes. When touching video-tool behavior, cover fallback paths because local ffmpeg availability can vary.

## Commit & Pull Request Guidelines

Git history is minimal, so there is no strict commit format yet. Use short imperative summaries such as `Add shot fallback test` or `Fix VLM response parsing`. Pull requests should include a brief purpose statement, test commands run, linked issue or plan when available, and screenshots or sample JSON when UI or prompt output changes.

## Security & Configuration Tips

Do not commit `.env`, API keys, commercial account credentials, or large private source videos. For real VLM calls, configure `VLM_API_BASE`, `VLM_API_KEY`, and `VLM_MODEL` locally; the deterministic analyzer should remain usable without secrets.
