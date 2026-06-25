from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.pipeline import AnalysisPipeline
from app.replication_state import ReplicationStateStore


class ReplicationHarness:
    def __init__(
        self,
        pipeline: Any | None = None,
        state_store: ReplicationStateStore | None = None,
    ) -> None:
        self.pipeline = pipeline or AnalysisPipeline()
        self.state_store = state_store or ReplicationStateStore()

    def run_loop1(
        self,
        project_id: str,
        video_dir: Path,
        source_path: Path,
        shots_dir: Path,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
        partial_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        result = self.pipeline.analyze(
            source_path,
            shots_dir,
            progress_callback=progress_callback,
            partial_callback=partial_callback,
        )
        self.state_store.write_completed_loop1(
            project_id=project_id,
            video_dir=video_dir,
            source_video=source_path,
            result=result,
        )
        return result
