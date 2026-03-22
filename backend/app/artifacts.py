from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel

from .models import ReviewerSummary, RunSummary

T = TypeVar("T", bound=BaseModel)


RUN_LAYOUT = [
    "inputs",
    "style_profiles",
    "parsed",
    "matching",
    "retrieval",
    "proposals",
    "evidence",
    "review",
    "summaries",
    "exports",
    "logs",
]


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        for name in RUN_LAYOUT:
            (self.root / name).mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)

    def write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=path.parent, encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False, default=str)
            handle.flush()
            temp_name = handle.name
        temp_path = Path(temp_name)
        for attempt in range(8):
            try:
                temp_path.replace(path)
                return
            except PermissionError:
                if attempt == 7:
                    temp_path.unlink(missing_ok=True)
                    raise
                time.sleep(0.05 * (attempt + 1))

    def append_jsonl(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def read_jsonl(self, path: Path) -> list[Any]:
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def write_model(self, path: Path, model: BaseModel) -> None:
        self.write_json(path, model.model_dump(mode="json"))

    def write_models_jsonl(self, path: Path, models: Iterable[BaseModel]) -> None:
        path.unlink(missing_ok=True)
        for model in models:
            self.append_jsonl(path, model.model_dump(mode="json"))

    def read_model(self, path: Path, model_cls: type[T]) -> T:
        return model_cls.model_validate(self.read_json(path))

    def read_models_jsonl(self, path: Path, model_cls: type[T]) -> list[T]:
        return [model_cls.model_validate(item) for item in self.read_jsonl(path)]

    def lookup_by_id(self, path: Path, key: str, value: str) -> Any | None:
        for item in self.read_jsonl(path):
            if item.get(key) == value:
                return item
        return None

    def copy_input(self, source: Path, dest_name: str) -> str:
        dest = self.path("inputs", dest_name)
        shutil.copy2(source, dest)
        return str(dest.relative_to(self.root))


def recompute_summaries(store: ArtifactStore) -> tuple[RunSummary, ReviewerSummary]:
    return (
        store.read_model(store.path("summaries", "run_summary.json"), RunSummary),
        store.read_model(store.path("summaries", "reviewer_summary.json"), ReviewerSummary),
    )
