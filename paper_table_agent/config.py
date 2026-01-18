from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field, field_validator

DEFAULT_EMPTY_VALUES = ["", "NA", "N/A", "null", "-", " "]


class ProviderConfig(BaseModel):
    base_url: str = "http://localhost:1234/v1"
    api_key: str | None = None
    model_header: str = "gpt-oss-20b"
    model_match: str = "gpt-oss-20b"
    model_extract: str = "gpt-oss-20b"
    model_query_helper: str = "gpt-oss-20b"
    max_prompt_chars: int = 26000
    mock_mode: bool = False
    mock_payloads_path: Path | None = None


class MatchingConfig(BaseModel):
    top_k: int = 10
    confidence_threshold: float = 0.75
    confidence_margin: float = 0.05
    year_tolerance: int = 1
    header_max_chars: int = 8000


class ExtractionConfig(BaseModel):
    groups: list[dict[str, Any]] = Field(default_factory=list)
    examples_per_col: int = 3
    max_chunks: int = 20
    retry_on_unclear: bool = True
    retry_extra_chunks: int = 6


class RetrievalConfig(BaseModel):
    top_k: int = 12
    rerank_k: int = 12
    max_context_chunks: int = 16
    max_context_tokens: int = 1800
    query_variants: int = 4
    use_query_expansion: bool = True
    use_hyde: bool = True
    rrf_k: int = 60
    embedding_backend: str = "tfidf"
    reranker_backend: str = "tfidf"
    use_reranker: bool = True


class OcrConfig(BaseModel):
    enable_ocr: bool = True
    ocr_trigger_min_chars_per_page: int = 400


class GrobidConfig(BaseModel):
    enable_grobid: bool = False
    server_url: str = "http://localhost:8070"
    parse_references: bool = False


class RunConfig(BaseModel):
    table_path: Path
    schema_sheet_name: str = "schema"
    schema_mode: str = "sheet"
    pdf_folder: Path
    title_col: str | None = None
    authors_col: str | None = None
    year_col: str | None = None
    treat_single_space_as_empty: bool = True
    verify_mode: bool = False
    fast_mode: bool = False
    max_success_mode: bool = True
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    ocr: OcrConfig = Field(default_factory=OcrConfig)
    grobid: GrobidConfig = Field(default_factory=GrobidConfig)
    max_workers: int = 1

    @field_validator("table_path", "pdf_folder")
    @classmethod
    def _path_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"Path does not exist: {value}")
        return value

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2)


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path

    @property
    def artifacts_dir(self) -> Path:
        return self.run_dir / "artifacts"

    @property
    def parsed_dir(self) -> Path:
        return self.artifacts_dir / "parsed"

    @property
    def retrieval_dir(self) -> Path:
        return self.artifacts_dir / "retrieval_indexes"

    @property
    def ocr_dir(self) -> Path:
        return self.artifacts_dir / "ocr"

    @property
    def thumbnails_dir(self) -> Path:
        return self.artifacts_dir / "thumbnails"

    @property
    def exports_dir(self) -> Path:
        return self.run_dir / "exports"

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def db_path(self) -> Path:
        return self.run_dir / "proposals.sqlite"

    def ensure(self) -> None:
        for path in [
            self.run_dir,
            self.artifacts_dir,
            self.parsed_dir,
            self.retrieval_dir,
            self.ocr_dir,
            self.thumbnails_dir,
            self.exports_dir,
            self.logs_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def create_run_paths(table_path: Path, root: Path | None = None) -> RunPaths:
    root_dir = root or Path("runs")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = root_dir / f"{timestamp}__{table_path.stem}"
    run_paths = RunPaths(run_dir=run_dir)
    run_paths.ensure()
    return run_paths


def load_prompt_versions(prompt_dir: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    if not prompt_dir.exists():
        return versions
    for prompt in prompt_dir.glob("*.md"):
        versions[prompt.name] = str(prompt.stat().st_mtime)
    return versions


def capture_run_config(config: RunConfig, run_paths: RunPaths, prompt_versions: dict[str, str]) -> None:
    payload = config.model_dump(mode="json")
    payload["prompt_versions"] = prompt_versions
    payload["git_commit"] = _git_commit_hash()
    run_config_path = run_paths.run_dir / "run_config.json"
    run_config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _git_commit_hash() -> str | None:
    head_path = Path(".git/HEAD")
    if not head_path.exists():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if head.startswith("ref:"):
        ref = head.split(" ", 1)[1]
        ref_path = Path(".git") / ref
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
    return head


def validate_schema_columns(required: Iterable[str], columns: Iterable[str]) -> list[str]:
    missing = [col for col in required if col not in columns]
    if missing:
        raise ValueError(f"Schema columns missing from data: {missing}")
    return missing
