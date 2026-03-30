from __future__ import annotations

import json
import os
from typing import Optional

import httpx
from pydantic import BaseModel, Field, model_validator

CANONICAL_PROVIDERS = {"lm_studio"}
PROVIDER_DISPLAY_NAMES = {"lm_studio": "LM Studio"}


class TextModelConfig(BaseModel):
    model_id: str = "default"
    temperature: float = 0.0
    max_tokens: int = 2048


class VisionModelConfig(BaseModel):
    model_id: str = "default"
    temperature: float = 0.0
    max_tokens: int = 2048


class ProviderConfig(BaseModel):
    token: str
    base_url: str = "http://localhost:1234"
    text_model: TextModelConfig = Field(default_factory=TextModelConfig)
    vision_model: Optional[VisionModelConfig] = None
    locality: str = "local"


class ParserConfig(BaseModel):
    backend: str = "docling"
    ocr_enabled: bool = False
    ocr_language: str = "en"
    allow_basic_fallback: bool = False  # T026a: allow pypdfium2 fallback if configured parser fails


class MatchingConfig(BaseModel):
    strategy: str = "title_authors"
    ambiguity_threshold: float = 0.85


class StyleProfileConfig(BaseModel):
    enabled: bool = True
    max_examples: int = 3


class RetrievalConfig(BaseModel):
    strategy: str = "semantic_chunks"
    chunk_size: int = 512
    top_k: int = 10


class FigureReviewConfig(BaseModel):
    enabled: bool = False
    max_figures_per_paper: int = 20


class ReviewConfig(BaseModel):
    max_proposals_per_cell: int = 1


class ExportConfig(BaseModel):
    highlight_changes: bool = True
    include_audit_log: bool = True


class RunConfig(BaseModel):
    table_path: str
    schema_path: Optional[str] = None
    pdf_dir: str
    output_dir: str = "./runs"
    verify_mode: bool = False
    provider: ProviderConfig
    parser: ParserConfig = Field(default_factory=ParserConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    style_profiles: StyleProfileConfig = Field(default_factory=StyleProfileConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    figure_review: FigureReviewConfig = Field(default_factory=FigureReviewConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)

    @model_validator(mode="after")
    def validate_provider_token(self) -> RunConfig:
        if self.provider.token not in CANONICAL_PROVIDERS:
            raise ValueError(
                f"Unknown provider token '{self.provider.token}'. "
                f"Supported providers: {sorted(CANONICAL_PROVIDERS)}. "
                f"For LM Studio, use 'lm_studio'."
            )
        return self


def load_config(path: str) -> RunConfig:
    """Load and parse config from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return RunConfig.model_validate(data)


def apply_overrides(config: RunConfig, overrides: dict) -> RunConfig:
    """Apply picker-driven overrides (table_path, schema_path, pdf_dir)."""
    data = config.model_dump()
    for k in ("table_path", "schema_path", "pdf_dir"):
        if k in overrides and overrides[k] is not None:
            data[k] = overrides[k]
    return RunConfig.model_validate(data)


class ReadinessResult:
    def __init__(self) -> None:
        self.ok: bool = True
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


async def check_readiness(config: RunConfig) -> ReadinessResult:
    """Check paths, schema, table, and provider reachability."""
    r = ReadinessResult()

    if not os.path.exists(config.table_path):
        r.fail(f"table_path does not exist: {config.table_path}")
    elif not os.access(config.table_path, os.R_OK):
        r.fail(f"table_path is not readable: {config.table_path}")

    if config.schema_path and not os.path.exists(config.schema_path):
        r.fail(f"schema_path does not exist: {config.schema_path}")
    elif config.schema_path and not os.access(config.schema_path, os.R_OK):
        r.fail(f"schema_path is not readable: {config.schema_path}")

    if not os.path.exists(config.pdf_dir):
        r.fail(f"pdf_dir does not exist: {config.pdf_dir}")
    elif not os.path.isdir(config.pdf_dir):
        r.fail(f"pdf_dir is not a directory: {config.pdf_dir}")

    output_dir = config.output_dir
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            r.fail(f"Cannot create output_dir: {e}")
    elif not os.access(output_dir, os.W_OK):
        r.fail(f"output_dir is not writable: {output_dir}")

    if config.provider.token == "lm_studio":
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{config.provider.base_url}/v1/models")
                if resp.status_code != 200:
                    r.fail(
                        f"LM Studio at {config.provider.base_url} returned HTTP {resp.status_code}. "
                        f"Is LM Studio running?"
                    )
        except Exception as e:
            r.fail(
                f"Cannot reach LM Studio at {config.provider.base_url}: {e}. "
                f"Is LM Studio running with a model loaded?"
            )

    # T026a / T031: Check parser and OCR dependencies
    from .parsing import check_parser_readiness, check_ocr_readiness
    parser_errors = check_parser_readiness(
        config.parser.backend,
        config.parser.allow_basic_fallback,
    )
    for err in parser_errors:
        r.fail(err)

    ocr_errors = check_ocr_readiness(config.parser.ocr_enabled)
    for err in ocr_errors:
        r.fail(err)

    return r
