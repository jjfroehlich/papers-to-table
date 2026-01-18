from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
import threading
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
    get_checkpoint_id,
    get_checkpoint_metadata,
    WRITES_IDX_MAP,
)


class SqliteSaver(BaseCheckpointSaver[str]):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT,
                checkpoint_ns TEXT,
                checkpoint_id TEXT,
                checkpoint_type TEXT,
                checkpoint_blob BLOB,
                metadata_type TEXT,
                metadata_blob BLOB,
                parent_checkpoint_id TEXT,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            );

            CREATE TABLE IF NOT EXISTS blobs (
                thread_id TEXT,
                checkpoint_ns TEXT,
                channel TEXT,
                version TEXT,
                value_type TEXT,
                value_blob BLOB,
                PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
            );

            CREATE TABLE IF NOT EXISTS writes (
                thread_id TEXT,
                checkpoint_ns TEXT,
                checkpoint_id TEXT,
                task_id TEXT,
                write_idx INTEGER,
                channel TEXT,
                value_type TEXT,
                value_blob BLOB,
                task_path TEXT,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx)
            );
                """
            )
            self.conn.commit()

    def _load_blobs(self, thread_id: str, checkpoint_ns: str, versions: dict[str, Any]) -> dict[str, Any]:
        channel_values: dict[str, Any] = {}
        for channel, version in versions.items():
            row = self.conn.execute(
                """
                SELECT value_type, value_blob
                FROM blobs
                WHERE thread_id = ? AND checkpoint_ns = ? AND channel = ? AND version = ?
                """,
                (thread_id, checkpoint_ns, channel, str(version)),
            ).fetchone()
            if row and row["value_type"] != "empty":
                channel_values[channel] = self.serde.loads_typed((row["value_type"], row["value_blob"]))
        return channel_values

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)
        if checkpoint_id:
            with self._lock:
                row = self.conn.execute(
                    """
                SELECT checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_checkpoint_id
                FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
                """,
                (thread_id, checkpoint_ns, checkpoint_id),
                ).fetchone()
            if not row:
                return None
        else:
            with self._lock:
                row = self.conn.execute(
                    """
                SELECT checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_checkpoint_id
                FROM checkpoints
                WHERE thread_id = ? AND checkpoint_ns = ?
                ORDER BY checkpoint_id DESC
                LIMIT 1
                """,
                (thread_id, checkpoint_ns),
                ).fetchone()
            if not row:
                return None
            checkpoint_id = row["checkpoint_id"]

        checkpoint = self.serde.loads_typed((row["checkpoint_type"], row["checkpoint_blob"]))
        metadata = self.serde.loads_typed((row["metadata_type"], row["metadata_blob"]))
        writes = self._load_writes(thread_id, checkpoint_ns, checkpoint_id)
        checkpoint = {
            **checkpoint,
            "channel_values": self._load_blobs(thread_id, checkpoint_ns, checkpoint["channel_versions"]),
        }
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": row["parent_checkpoint_id"],
                    }
                }
                if row["parent_checkpoint_id"]
                else None
            ),
            pending_writes=[(task_id, channel, self.serde.loads_typed(value)) for task_id, channel, value in writes],
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        if not config:
            return iter(())
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        params: list[Any] = [thread_id, checkpoint_ns]
        query = (
            "SELECT checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_checkpoint_id "
            "FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? ORDER BY checkpoint_id DESC"
        )
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        for row in rows[:limit or len(rows)]:
            checkpoint_id = row["checkpoint_id"]
            checkpoint = self.serde.loads_typed((row["checkpoint_type"], row["checkpoint_blob"]))
            metadata = self.serde.loads_typed((row["metadata_type"], row["metadata_blob"]))
            if filter and not all(metadata.get(k) == v for k, v in filter.items()):
                continue
            checkpoint = {
                **checkpoint,
                "channel_values": self._load_blobs(thread_id, checkpoint_ns, checkpoint["channel_versions"]),
            }
            writes = self._load_writes(thread_id, checkpoint_ns, checkpoint_id)
            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": row["parent_checkpoint_id"],
                        }
                    }
                    if row["parent_checkpoint_id"]
                    else None
                ),
                pending_writes=[(task_id, channel, self.serde.loads_typed(value)) for task_id, channel, value in writes],
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict[str, Any],
    ) -> RunnableConfig:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        values = checkpoint["channel_values"]
        for channel, version in new_versions.items():
            if channel in values:
                value_type, value_blob = self.serde.dumps_typed(values[channel])
            else:
                value_type, value_blob = ("empty", b"")
            with self._lock:
                self.conn.execute(
                    """
                INSERT OR REPLACE INTO blobs
                (thread_id, checkpoint_ns, channel, version, value_type, value_blob)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, checkpoint_ns, channel, str(version), value_type, value_blob),
                )

        checkpoint_data = checkpoint.copy()
        checkpoint_data.pop("channel_values", None)
        checkpoint_type, checkpoint_blob = self.serde.dumps_typed(checkpoint_data)
        metadata_type, metadata_blob = self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
        parent_id = config["configurable"].get("checkpoint_id")
        with self._lock:
            self.conn.execute(
                """
            INSERT OR REPLACE INTO checkpoints
            (thread_id, checkpoint_ns, checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_checkpoint_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (thread_id, checkpoint_ns, checkpoint_id, checkpoint_type, checkpoint_blob, metadata_type, metadata_blob, parent_id),
            )
            self.conn.commit()
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id: str = config["configurable"]["checkpoint_id"]
        for idx, (channel, value) in enumerate(writes):
            write_idx = WRITES_IDX_MAP.get(channel, idx)
            if write_idx < 0:
                continue
            value_type, value_blob = self.serde.dumps_typed(value)
            with self._lock:
                self.conn.execute(
                    """
                INSERT OR REPLACE INTO writes
                (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, value_type, value_blob, task_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (thread_id, checkpoint_ns, checkpoint_id, task_id, write_idx, channel, value_type, value_blob, task_path),
                )
        with self._lock:
            self.conn.commit()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            self.conn.execute("DELETE FROM blobs WHERE thread_id = ?", (thread_id,))
            self.conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
            self.conn.commit()

    def _load_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[tuple[str, str, tuple[str, bytes]]]:
        with self._lock:
            rows = self.conn.execute(
                """
            SELECT task_id, channel, value_type, value_blob
            FROM writes
            WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?
            ORDER BY write_idx
            """,
            (thread_id, checkpoint_ns, checkpoint_id),
            ).fetchall()
        return [(row["task_id"], row["channel"], (row["value_type"], row["value_blob"])) for row in rows]
