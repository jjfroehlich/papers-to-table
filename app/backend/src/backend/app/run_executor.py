from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections.abc import Awaitable, Callable
from typing import Optional, Protocol

from .config import RunConfig


class RunExecutor(Protocol):
    def launch(
        self,
        run_id: str,
        config: RunConfig,
        config_path: Optional[str],
        output_dir: str,
        resolved_inputs: Optional[dict[str, object]] = None,
    ) -> None: ...

    async def abort(self, run_id: str) -> bool: ...


@dataclass
class LocalAsyncRunExecutor:
    pipeline_runner: Callable[..., Awaitable[None]]

    def __post_init__(self) -> None:
        self._active_runs: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def launch(
        self,
        run_id: str,
        config: RunConfig,
        config_path: Optional[str],
        output_dir: str,
        resolved_inputs: Optional[dict[str, object]] = None,
    ) -> None:
        async def _register_and_run() -> None:
            async with self._lock:
                task = asyncio.current_task()
                self._active_runs[run_id] = task  # type: ignore[assignment]
            try:
                await self.pipeline_runner(
                    run_id,
                    config,
                    config_path,
                    output_dir,
                    resolved_inputs=resolved_inputs,
                )
            finally:
                async with self._lock:
                    self._active_runs.pop(run_id, None)

        asyncio.create_task(_register_and_run())

    async def abort(self, run_id: str) -> bool:
        async with self._lock:
            task = self._active_runs.get(run_id)
            if task is None:
                return False
            task.cancel()
            return True


_executor: RunExecutor | None = None


def configure_run_executor(executor: RunExecutor) -> None:
    global _executor
    _executor = executor


def get_run_executor() -> RunExecutor:
    if _executor is None:
        raise RuntimeError('Run executor is not configured.')
    return _executor
