from __future__ import annotations

import asyncio
import pathlib
from typing import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ...artifacts import get_run_json_path, list_run_ids, read_json
from ...run_events import encode_sse, subscribe_to_run_events
from ...settings import load_app_settings
from ..common import validate_output_dir_access

router = APIRouter()


def _bootstrap_payload(output_dir: str, run_id: str | None = None) -> dict:
    if run_id:
        path = get_run_json_path(output_dir, run_id)
        runs = [read_json(path)] if path.exists() else []
    else:
        runs = []
        for existing_run_id in list_run_ids(output_dir):
            try:
                runs.append(read_json(get_run_json_path(output_dir, existing_run_id)))
            except Exception:
                pass
    runs.sort(key=lambda item: item.get('created_at', ''), reverse=True)
    return {'runs': runs}


@router.get('/api/runs/events')
async def stream_run_events(request: Request, output_dir: str = './runs', run_id: str | None = None):
    validate_output_dir_access(output_dir)
    settings = getattr(request.app.state, 'app_settings', load_app_settings())

    async def event_stream() -> AsyncIterator[str]:
        yield encode_sse('bootstrap', _bootstrap_payload(output_dir, run_id=run_id))
        async with subscribe_to_run_events(run_id=run_id) as queue:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=settings.sse_ping_seconds)
                    event_run = event.get('run') or {}
                    event_output_dir = event_run.get('output_dir')
                    if run_id is None and event_output_dir:
                        if pathlib.Path(event_output_dir).resolve() != pathlib.Path(output_dir).resolve():
                            continue
                    yield encode_sse(event.get('event', 'message'), event)
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'

    return StreamingResponse(event_stream(), media_type='text/event-stream')
