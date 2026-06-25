from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import load_config
from app.harness import ReplicationHarness
from app.logging_config import logger
from app.models import NewContentInput, ShotGrammar
from app.pipeline import AnalysisPipeline
from app.prompt_compiler import PromptCompiler
from app.replication_state import ReplicationStateStore
from app.storage import VideoStorage
from app.vlm_client import OpenAICompatibleVLMClient


config = load_config()
storage = VideoStorage(config.data_root)
pipeline = AnalysisPipeline()
harness = ReplicationHarness(pipeline=pipeline)
compiler = PromptCompiler()
state_store = ReplicationStateStore()

app = FastAPI(title="Video-to-Shot-Grammar Prompt System")
analysis_jobs: dict[str, dict[str, Any]] = {}


class CompileRequest(BaseModel):
    shot_grammar: list[dict[str, Any]]
    new_content: dict[str, str]


class ReplicateRequest(BaseModel):
    shot_grammar: list[dict[str, Any]]
    aspect_ratio: str = "16:9"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
def upload_video(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only mp4 uploads are supported")

    workspace = storage.create_workspace(file.filename)
    with workspace.source_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    return {
        "video_id": workspace.video_id,
        "source_path": str(workspace.source_path),
    }


@app.post("/api/videos/{video_id}/analyze")
def analyze_video(video_id: str) -> dict[str, object]:
    workspace = _workspace_for(video_id)
    if not workspace["source_path"].exists():
        raise HTTPException(status_code=404, detail="Video not found")

    try:
        result = harness.run_loop1(
            project_id=video_id,
            video_dir=workspace["video_dir"],
            source_path=workspace["source_path"],
            shots_dir=workspace["shots_dir"],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _write_analysis_outputs(workspace["video_dir"], result)
    return result


@app.post("/api/videos/{video_id}/analyze/start")
def start_analyze_video(
    video_id: str, background_tasks: BackgroundTasks
) -> dict[str, str]:
    workspace = _workspace_for(video_id)
    if not workspace["source_path"].exists():
        raise HTTPException(status_code=404, detail="Video not found")

    job_id = uuid4().hex[:12]
    analysis_jobs[job_id] = {
        "job_id": job_id,
        "video_id": video_id,
        "status": "running",
        "stage": "queued",
        "message": "正在排队分析，较长视频可能需要几分钟。",
        "progress": 0,
        "current": 0,
        "total": 0,
        "result": None,
        "error": None,
    }
    logger.info("analysis_job_created job_id=%s video_id=%s", job_id, video_id)
    background_tasks.add_task(_run_analysis_job, job_id, video_id)
    return {
        "job_id": job_id,
        "status": "running",
        "message": analysis_jobs[job_id]["message"],
    }


@app.get("/api/analysis-jobs/{job_id}")
def get_analysis_job(job_id: str) -> dict[str, Any]:
    job = analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return job


@app.get("/api/videos/latest-analysis")
def get_latest_analysis() -> dict[str, object]:
    videos_dir = config.data_root / "videos"
    if not videos_dir.exists():
        raise HTTPException(status_code=404, detail="Analysis not found")

    candidates = []
    for analysis_path in videos_dir.glob("*/analysis.json"):
        if analysis_path.is_file():
            candidates.append(analysis_path)
    if not candidates:
        raise HTTPException(status_code=404, detail="Analysis not found")

    result_path = max(candidates, key=lambda path: path.stat().st_mtime)
    return {
        "video_id": result_path.parent.name,
        "analysis": json.loads(result_path.read_text(encoding="utf-8")),
    }


@app.get("/api/videos/{video_id}/analysis")
def get_analysis(video_id: str) -> dict[str, object]:
    result_path = _workspace_for(video_id)["video_dir"] / "analysis.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="Analysis not found")
    return json.loads(result_path.read_text(encoding="utf-8"))


@app.get("/api/videos/{video_id}/media/source")
def get_source_video(video_id: str) -> FileResponse:
    source_path = _workspace_for(video_id)["source_path"]
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(source_path, media_type="video/mp4")


@app.get("/api/videos/{video_id}/shots/{shot_id}/{filename}")
def get_keyframe(video_id: str, shot_id: str, filename: str) -> FileResponse:
    allowed = {"frame_start.jpg", "frame_mid.jpg", "frame_end.jpg"}
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="Keyframe not found")
    frame_path = _workspace_for(video_id)["shots_dir"] / shot_id / filename
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Keyframe not found")
    return FileResponse(frame_path, media_type="image/jpeg")


@app.post("/api/compile")
def compile_prompts(request: CompileRequest) -> dict[str, object]:
    grammars = [ShotGrammar(**item) for item in request.shot_grammar]
    new_content = NewContentInput(**request.new_content)
    return compiler.compile(grammars, new_content)


@app.post("/api/replicate")
def compile_replicate_prompts(request: ReplicateRequest) -> dict[str, object]:
    grammars = [ShotGrammar(**item) for item in request.shot_grammar]
    return compiler.compile_replicate(grammars, aspect_ratio=request.aspect_ratio)


@app.post("/api/videos/{video_id}/compile")
def compile_video_prompts(video_id: str, new_content: dict[str, str]) -> dict[str, object]:
    analysis = get_analysis(video_id)
    grammars = [ShotGrammar(**item) for item in analysis["shot_grammar"]]
    return compiler.compile(grammars, NewContentInput(**new_content))


@app.post("/api/videos/{video_id}/replicate")
def compile_video_replicate_prompts(
    video_id: str, payload: dict[str, str] | None = None
) -> dict[str, object]:
    analysis = get_analysis(video_id)
    grammars = [ShotGrammar(**item) for item in analysis["shot_grammar"]]
    aspect_ratio = (payload or {}).get("aspect_ratio") or analysis.get("video_info", {}).get(
        "aspect_ratio", "16:9"
    )
    return compiler.compile_replicate(grammars, aspect_ratio=aspect_ratio)


@app.post("/api/videos/{video_id}/replicate/llm")
def compile_video_replicate_prompts_with_llm(
    video_id: str, payload: dict[str, Any] | None = None
) -> dict[str, object]:
    workspace = _workspace_for(video_id)
    analysis = get_analysis(video_id)
    grammars = [ShotGrammar(**item) for item in analysis["shot_grammar"]]
    aspect_ratio = (payload or {}).get("aspect_ratio") or analysis.get("video_info", {}).get(
        "aspect_ratio", "16:9"
    )
    result = compiler.compile_replicate_with_llm(
        grammars,
        client=_build_vlm_client(),
        aspect_ratio=aspect_ratio,
        max_workers=int((payload or {}).get("max_workers") or 4),
    )
    result_path = workspace["video_dir"] / "replicate_prompts.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    state_store.record_prompt_generation(workspace["video_dir"], result)
    logger.info(
        "replicate_prompts_saved video_id=%s path=%s prompts=%s",
        video_id,
        result_path,
        len(result.get("generated_prompts", [])),
    )
    return result


@app.post("/api/export/markdown", response_class=PlainTextResponse)
def export_markdown(payload: dict[str, Any]) -> str:
    prompts = payload.get("generated_prompts", [])
    lines = [f"# {payload.get('global_style_prompt', 'Generated Prompts')}", ""]
    for item in prompts:
        lines.extend(
            [
                f"## {item['shot_id']} ({item['duration']})",
                "",
                item["prompt"],
                "",
                "**Negative Prompt**",
                "",
                item["negative_prompt"],
                "",
            ]
        )
    return "\n".join(lines)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


def _workspace_for(video_id: str) -> dict[str, Path]:
    video_dir = config.data_root / "videos" / video_id
    return {
        "video_dir": video_dir,
        "source_path": video_dir / "source.mp4",
        "shots_dir": video_dir / "shots",
    }


def _build_vlm_client() -> OpenAICompatibleVLMClient:
    if not config.vlm_api_base or not config.vlm_api_key or not config.vlm_model:
        raise HTTPException(status_code=500, detail="VLM config is missing")
    return OpenAICompatibleVLMClient(
        api_base=config.vlm_api_base,
        api_key=config.vlm_api_key,
        model=config.vlm_model,
    )


def _run_analysis_job(job_id: str, video_id: str) -> None:
    workspace = _workspace_for(video_id)
    try:
        def update_progress(event: dict[str, Any]) -> None:
            analysis_jobs[job_id].update(event)
            logger.info(
                "analysis_job_progress job_id=%s video_id=%s stage=%s progress=%s current=%s total=%s message=%s",
                job_id,
                video_id,
                event.get("stage"),
                event.get("progress"),
                event.get("current"),
                event.get("total"),
                event.get("message"),
            )

        logger.info("analysis_job_started job_id=%s video_id=%s", job_id, video_id)
        def persist_partial(partial: dict[str, Any]) -> None:
            _write_partial_analysis(workspace["video_dir"], partial)

        result = harness.run_loop1(
            project_id=video_id,
            video_dir=workspace["video_dir"],
            source_path=workspace["source_path"],
            shots_dir=workspace["shots_dir"],
            progress_callback=update_progress,
            partial_callback=persist_partial,
        )
        _write_analysis_outputs(workspace["video_dir"], result)
        analysis_jobs[job_id].update(
            {
                "status": "completed",
                "stage": "completed",
                "message": "分析完成",
                "progress": 100,
                "result": result,
                "error": None,
            }
        )
        logger.info("analysis_job_completed job_id=%s video_id=%s", job_id, video_id)
    except Exception as exc:
        analysis_jobs[job_id].update(
            {
                "status": "failed",
                "stage": "failed",
                "message": "分析失败",
                "result": None,
                "error": str(exc),
            }
        )
        logger.exception(
            "analysis_job_failed job_id=%s video_id=%s error=%s",
            job_id,
            video_id,
            exc,
        )


def _write_partial_analysis(video_dir: Path, partial: dict[str, Any]) -> None:
    partial_path = video_dir / "analysis.partial.json"
    partial_path.write_text(
        json.dumps(partial, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shot = partial.get("shot", {})
    grammar = partial.get("grammar")
    shot_id = shot.get("shot_id")
    if shot_id and grammar:
        shot_dir = video_dir / "shots" / shot_id
        shot_dir.mkdir(parents=True, exist_ok=True)
        (shot_dir / "shot_grammar.json").write_text(
            json.dumps(grammar, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            "partial_grammar_saved video_id=%s shot_id=%s path=%s",
            video_dir.name,
            shot_id,
            shot_dir / "shot_grammar.json",
        )


def _write_analysis_outputs(video_dir: Path, result: dict[str, Any]) -> None:
    analysis_path = video_dir / "analysis.json"
    analysis_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    shot_list = {
        "video_info": result.get("video_info", {}),
        "candidate_shots": result.get("candidate_shots", []),
        "scenes": result.get("scenes", []),
        "shots": result.get("shots", []),
        "context_tracks": result.get("context_tracks", {}),
        "keyframes": result.get("keyframes", []),
    }
    (video_dir / "shot_list.json").write_text(
        json.dumps(shot_list, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
