from __future__ import annotations

from pathlib import Path

from jinja2 import Template

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


def render_prompt(name: str, **kwargs: str) -> str:
    prompt_path = PROMPT_DIR / name
    template = Template(prompt_path.read_text(encoding="utf-8"))
    return template.render(**kwargs)
