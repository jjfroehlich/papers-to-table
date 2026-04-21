from __future__ import annotations

import os
from dataclasses import dataclass, field


def _split_csv(value: str | None, *, default: list[str]) -> list[str]:
    if value is None:
        return list(default)
    parts = [item.strip() for item in value.split(',') if item.strip()]
    return parts or list(default)


@dataclass(frozen=True)
class AppSettings:
    cors_allowed_origins: list[str] = field(
        default_factory=lambda: ['http://localhost:5173', 'http://127.0.0.1:5173']
    )
    cors_allowed_methods: list[str] = field(default_factory=lambda: ['GET', 'POST', 'OPTIONS'])
    cors_allowed_headers: list[str] = field(default_factory=lambda: ['*'])
    cors_allow_credentials: bool = False
    sse_ping_seconds: float = 10.0


def load_app_settings() -> AppSettings:
    return AppSettings(
        cors_allowed_origins=_split_csv(
            os.getenv('PAPER_APP_CORS_ORIGINS'),
            default=['http://localhost:5173', 'http://127.0.0.1:5173'],
        ),
        cors_allowed_methods=_split_csv(
            os.getenv('PAPER_APP_CORS_METHODS'),
            default=['GET', 'POST', 'OPTIONS'],
        ),
        cors_allowed_headers=_split_csv(
            os.getenv('PAPER_APP_CORS_HEADERS'),
            default=['*'],
        ),
        cors_allow_credentials=os.getenv('PAPER_APP_CORS_ALLOW_CREDENTIALS', 'false').lower() == 'true',
        sse_ping_seconds=float(os.getenv('PAPER_APP_SSE_PING_SECONDS', '10')),
    )
