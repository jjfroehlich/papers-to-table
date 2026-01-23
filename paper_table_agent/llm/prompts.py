from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def render_prompt(name: str, **kwargs: str) -> str:
    prompt_meta = kwargs.pop("_prompt_meta", None) or {}
    prompt_meta = {"prompt_name": name, **prompt_meta}
    prompt_path = PROMPT_DIR / name
    template = Template(prompt_path.read_text(encoding="utf-8"))
    rendered = template.render(**kwargs)
    return f"PROMPT_META: {json.dumps(prompt_meta, sort_keys=True)}\n{rendered}"
