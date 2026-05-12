from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

from .constants import CANONICAL_PROVIDERS, CANONICAL_RETRIEVAL_MODES, DEFAULT_MODEL_ID, LEGACY_RETRIEVAL_MODE_ALIASES


class TextModelConfig(BaseModel):
    model_id: str = DEFAULT_MODEL_ID
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    min_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    chat_template_kwargs: dict[str, Any] = Field(default_factory=dict)
    working_context_budget: int = Field(default=12000, ge=1)
    load_context_length: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode='after')
    def validate_context_contract(self) -> 'TextModelConfig':
        if self.load_context_length is not None and self.load_context_length < self.working_context_budget:
            raise ValueError(
                'provider.text_model.load_context_length must be greater than or equal to '
                'provider.text_model.working_context_budget.'
            )
        return self

    @property
    def required_load_context_length(self) -> int:
        return int(self.load_context_length or self.working_context_budget)

    @property
    def load_context_is_derived(self) -> bool:
        return self.load_context_length is None


class VisionModelConfig(BaseModel):
    model_id: str = DEFAULT_MODEL_ID
    temperature: float = 0.0
    max_tokens: int = 2048
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    min_p: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    extra_body: dict[str, Any] = Field(default_factory=dict)
    chat_template_kwargs: dict[str, Any] = Field(default_factory=dict)
    load_context_length: Optional[int] = Field(default=None, ge=1)


class ProviderConfig(BaseModel):
    token: str
    base_url: str = 'http://localhost:1234'
    text_model: TextModelConfig = Field(default_factory=TextModelConfig)
    vision_model: Optional[VisionModelConfig] = None
    locality: str = 'local'


class ParserConfig(BaseModel):
    backend: str = 'docling'
    ocr_enabled: bool = False
    ocr_language: str = 'en'
    allow_basic_fallback: bool = False
    cache_enabled: bool = True
    cache_dir: Optional[str] = None


class MatchingConfig(BaseModel):
    strategy: str = 'title_authors'
    ambiguity_threshold: float = 0.15


class StyleProfileConfig(BaseModel):
    enabled: bool = True
    max_examples: int = 3
    normal_mode_behavior: str = 'sample_rows'
    eval_mode_behavior: str = 'masked_rows'

    @model_validator(mode='after')
    def validate_behavior(self) -> 'StyleProfileConfig':
        valid_normal = {'sample_rows', 'disabled'}
        valid_eval = {'masked_rows', 'disabled'}
        if self.normal_mode_behavior not in valid_normal:
            raise ValueError(
                'style_profiles.normal_mode_behavior must be one of: '
                f'{sorted(valid_normal)}.'
            )
        if self.eval_mode_behavior not in valid_eval:
            raise ValueError(
                'style_profiles.eval_mode_behavior must be one of: '
                f'{sorted(valid_eval)}.'
            )
        return self

    def resolve_behavior(self, run_mode: str) -> tuple[str, str, bool]:
        if not self.enabled:
            return 'disabled', 'disabled', run_mode == 'eval'
        if run_mode == 'eval':
            if self.eval_mode_behavior == 'disabled':
                return 'disabled', 'disabled', True
            return 'masked_rows', 'masked_working_copy', True
        if self.normal_mode_behavior == 'disabled':
            return 'disabled', 'disabled', False
        return 'sample_rows', 'filled_cells', False


class RetrievalConfig(BaseModel):
    mode: str = 'hybrid_experimental'
    top_k: int = 12
    recall_rescue_enabled: bool = False
    whole_document_mode: bool = False
    whole_document_max_chars: int = 20000

    @model_validator(mode='before')
    @classmethod
    def normalize_mode(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        raw_mode = normalized.get('mode')
        if raw_mode is None and 'strategy' in normalized:
            raw_mode = normalized.pop('strategy')
        elif 'strategy' in normalized:
            normalized.pop('strategy')

        mode = str(raw_mode or 'hybrid_experimental').strip().lower()
        normalized['mode'] = LEGACY_RETRIEVAL_MODE_ALIASES.get(mode, mode)
        return normalized

    @model_validator(mode='after')
    def validate_mode(self) -> 'RetrievalConfig':
        if self.mode not in CANONICAL_RETRIEVAL_MODES:
            raise ValueError(
                f"Unknown retrieval.mode '{self.mode}'. "
                f'Supported retrieval modes: {sorted(CANONICAL_RETRIEVAL_MODES)}.'
            )
        return self

    @property
    def strategy(self) -> str:
        return self.mode


class FigureReviewConfig(BaseModel):
    enabled: bool = False
    max_figures_per_paper: int = 20
    skip_when_prompt_only_degraded: bool = True


class ReviewConfig(BaseModel):
    max_proposals_per_cell: int = 1


class ExportConfig(BaseModel):
    highlight_changes: bool = True
    include_audit_log: bool = True


class PromptConfig(BaseModel):
    bundle: Optional[str] = None
    bundle_path: Optional[str] = None


class DiagnosticsConfig(BaseModel):
    verbose_provider_logging: bool = False
    provider_preview_chars: int = 240


class RunConfig(BaseModel):
    table_path: str
    schema_path: Optional[str] = None
    pdf_dir: str
    output_dir: str = './runs'
    verify_mode: bool = False
    eval_mode: bool = False
    provider: ProviderConfig
    parser: ParserConfig = Field(default_factory=ParserConfig)
    matching: MatchingConfig = Field(default_factory=MatchingConfig)
    style_profiles: StyleProfileConfig = Field(default_factory=StyleProfileConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    figure_review: FigureReviewConfig = Field(default_factory=FigureReviewConfig)
    review: ReviewConfig = Field(default_factory=ReviewConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    prompt: PromptConfig = Field(default_factory=PromptConfig)
    diagnostics: DiagnosticsConfig = Field(default_factory=DiagnosticsConfig)

    @model_validator(mode='after')
    def validate_provider_token(self) -> 'RunConfig':
        if self.provider.token not in CANONICAL_PROVIDERS:
            raise ValueError(
                f"Unknown provider token '{self.provider.token}'. "
                f'Supported providers: {sorted(CANONICAL_PROVIDERS)}. '
                "For LM Studio, use 'lm_studio'."
            )
        if self.verify_mode and self.eval_mode:
            raise ValueError(
                'verify_mode=true and eval_mode=true cannot be used together. '
                'Use verify_mode for reviewer comparison on filled cells, or eval_mode '
                'for leakage-safe benchmark runs with a masked working copy.'
            )
        return self


def get_run_mode(config: RunConfig) -> str:
    if config.verify_mode and config.eval_mode:
        raise ValueError(
            'verify_mode=true and eval_mode=true cannot be used together. '
            'Disable one mode before starting the run.'
        )
    if config.eval_mode:
        return 'eval'
    if config.verify_mode:
        return 'verify'
    return 'normal'
