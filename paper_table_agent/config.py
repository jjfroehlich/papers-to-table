from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, Field, field_validator

from paper_table_agent.text.normalization import normalize_key

DEFAULT_EMPTY_VALUES = ["", "NA", "N/A", "null", "-", " ", "nan", "NaN", "—"]


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _env_optional_int(key: str, default: int | None) -> int | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    lowered = value.strip().lower()
    if lowered in {"none", "null", "off"}:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else None


class ProviderConfig(BaseModel):
    mode: str = "openai"
    base_url: str = "http://localhost:1234/v1"
    api_key: str | None = None
    model_header: str = "gpt-oss-20b"
    model_match: str = "gpt-oss-20b"
    model_extract: str = "gpt-oss-20b"
    model_query_helper: str = "gpt-oss-20b"
    fallback_enabled: bool = False
    fallback_base_url: str | None = None
    fallback_api_key: str | None = None
    fallback_model_header: str | None = None
    fallback_model_match: str | None = None
    fallback_model_extract: str | None = None
    fallback_model_query_helper: str | None = None
    max_prompt_chars: int = Field(default_factory=lambda: _env_int("PAPER_TABLE_AGENT_MAX_PROMPT_CHARS", 64000))
    max_prompt_tokens: int | None = Field(
        default_factory=lambda: _env_optional_int("PAPER_TABLE_AGENT_MAX_PROMPT_TOKENS", None)
    )
    ctx_window_tokens_override: int | None = Field(
        default_factory=lambda: _env_optional_int("PAPER_TABLE_AGENT_CTX_WINDOW_TOKENS", None)
    )
    timeout_s: float = 60.0
    read_timeout_s: float = 180.0
    mock_mode: bool = False
    mock_payloads_path: Path | None = None
    guided_json_mode: str = Field(
        default="auto",
        description=(
            "Guided JSON mode for response_format/json_schema. 'auto' disables guided mode for local/private "
            "endpoints or when health checks detect schema rejections; prompt-only JSON remains the fallback."
        ),
    )
    llm_debug: bool = False
    record_requests: bool = False
    record_path: Path | None = None
    record_payloads: bool = False
    payload_record_path: Path | None = None
    measure_prompt_tokens: bool = False


class MatchingConfig(BaseModel):
    top_k: int = 10
    confidence_threshold: float = 0.75
    confidence_margin: float = 0.05
    fallback_min: float = 0.5
    fallback_threshold: float = 0.45
    fallback_margin: float = 0.1
    year_tolerance: int = 1
    header_max_chars: int = 8000


class ExtractionConfig(BaseModel):
    groups: list[dict[str, Any]] = Field(default_factory=list)
    examples_per_col: int = 3
    column_batch_size: int = 2
    max_chunks: int = 20
    retry_on_unclear: bool = True
    retry_extra_chunks: int = 10
    whole_text_enabled: bool = True
    whole_text_max_tokens: int = 6000
    fulltext_target_ratio: float = 0.85
    fulltext_caption_max_chars: int = 240
    paper_memory_enabled: bool = True
    paper_memory_max_tokens: int = 1200
    thinking_models: list[str] = Field(default_factory=lambda: ["gpt-oss", "qwen"])


class RetrievalConfig(BaseModel):
    top_k: int = 20
    rerank_k: int = 20
    max_context_chunks: int = 24
    max_context_tokens: int = 2400
    context_window: int = 1
    include_section_chunks: bool = True
    section_chunk_limit: int = 6
    summary_enabled: bool = True
    summary_max_chunks: int = 12
    summary_max_tokens: int = 1000
    query_variants: int = 6
    use_query_expansion: bool = True
    use_hyde: bool = True
    rrf_k: int = 60
    use_dense: bool = True
    embedding_backend: str = "tfidf"
    embedding_model: str | None = None
    reranker_backend: str = "tfidf"
    reranker_model: str | None = None
    use_reranker: bool = True
    query_cache_max_entries: int = 256
    hyde_cache_max_entries: int = 256


class OcrConfig(BaseModel):
    enable_ocr: bool = True
    ocr_trigger_min_chars_per_page: int = 400
    whitespace_ratio_min: float = 0.06
    avg_token_length_max: float = 18.0


class GrobidConfig(BaseModel):
    enable_grobid: bool = False
    server_url: str = "http://localhost:8070"
    parse_references: bool = False


class OutputConfig(BaseModel):
    debug_reports: bool = False


class AuditConfig(BaseModel):
    use_filled_cells_as_gold: bool = True
    sample_rate: float | None = None
    max_cells: int | None = 500
    columns_allowlist: list[str] = Field(default_factory=list)
    columns_denylist: list[str] = Field(default_factory=list)
    numeric_tolerance_by_column: dict[str, float] = Field(default_factory=dict)
    categorical_aliases_by_column: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    text_similarity_threshold: float = 0.6


class RunConfig(BaseModel):
    table_path: Path
    schema_sheet_name: str = "schema"
    schema_mode: str = "sheet"
    schema_path: Path | None = None
    run_name: str | None = None
    pdf_folder: Path
    title_col: str | None = None
    authors_col: str | None = None
    year_col: str | None = None
    doi_col: str | None = None
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
    output: OutputConfig = Field(default_factory=OutputConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    max_workers: int = 1

    @field_validator("table_path", "pdf_folder")
    @classmethod
    def _path_exists(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"Path does not exist: {value}")
        return value

    @field_validator("schema_path")
    @classmethod
    def _schema_path_exists(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
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


def create_run_paths(table_path: Path, root: Path | None = None, run_name: str | None = None) -> RunPaths:
    env_root = os.getenv("PAPER_TABLE_AGENT_RUNS_ROOT")
    root_dir = Path(env_root) if env_root else (root or Path("runs"))
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = _slugify_run_name(run_name) or table_path.stem
    run_dir = root_dir / f"{timestamp}__{slug}"
    run_paths = RunPaths(run_dir=run_dir)
    run_paths.ensure()
    return run_paths


def _slugify_run_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^0-9A-Za-z]+", "-", value.strip()).strip("-")
    return cleaned.lower()


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
    required_list = list(required)
    column_list = list(columns)
    required_keys = {normalize_key(col): col for col in required_list}
    column_keys = {normalize_key(col): col for col in column_list}
    missing = [required_keys[key] for key in required_keys if key not in column_keys]
    if missing:
        raise ValueError(f"Schema columns missing from data: {missing}")
    return missing
