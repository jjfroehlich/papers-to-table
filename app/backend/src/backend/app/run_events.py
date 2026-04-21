from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Subscriber:
    queue: asyncio.Queue[dict[str, Any]]
    run_id: str | None = None


class RunEventBroker:
    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            subscriber_run_id = subscriber.run_id
            if subscriber_run_id is not None and event.get('run_id') != subscriber_run_id:
                continue
            subscriber.queue.put_nowait(event)

    @asynccontextmanager
    async def subscribe(self, run_id: str | None = None) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        subscriber = Subscriber(queue=asyncio.Queue(), run_id=run_id)
        async with self._lock:
            self._subscribers.add(subscriber)
        try:
            yield subscriber.queue
        finally:
            async with self._lock:
                self._subscribers.discard(subscriber)


_broker = RunEventBroker()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


async def publish_run_update(run_data: dict[str, Any]) -> None:
    await _broker.publish(
        {
            'event': 'run.updated',
            'run_id': run_data.get('run_id'),
            'recorded_at': _timestamp(),
            'run': run_data,
        }
    )


async def publish_run_deleted(run_id: str) -> None:
    await _broker.publish(
        {
            'event': 'run.deleted',
            'run_id': run_id,
            'recorded_at': _timestamp(),
        }
    )


@asynccontextmanager
async def subscribe_to_run_events(run_id: str | None = None) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
    async with _broker.subscribe(run_id=run_id) as queue:
        yield queue


def encode_sse(event: str, payload: dict[str, Any]) -> str:
    return f'event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'
