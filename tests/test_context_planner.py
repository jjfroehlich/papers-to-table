from __future__ import annotations

from paper_table_agent.config import ExtractionConfig
from paper_table_agent.graph.context_planner import _trim_fulltext


def test_fulltext_trimming_drops_references_first() -> None:
    config = ExtractionConfig()
    text = "\n".join(
        [
            "Introduction",
            "We describe the method.",
            "Acknowledgements",
            "Thanks to collaborators.",
            "References",
            "1. Example Ref",
        ]
    )
    trimmed, _sections, steps = _trim_fulltext(text, config)
    assert "References" not in trimmed
    assert "Acknowledgements" not in trimmed
    assert "drop_references" in steps
