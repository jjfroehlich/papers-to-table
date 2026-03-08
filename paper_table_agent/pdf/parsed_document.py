from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedElement:
    element_id: str
    element_type: str
    text: str
    page_start: int
    page_end: int
    order: int
    heading: str | None = None
    bbox: list[float] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    pdf_id: str
    title: str | None
    page_text: list[str]
    elements: list[ParsedElement]

    def element_type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for element in self.elements:
            counts[element.element_type] = counts.get(element.element_type, 0) + 1
        return counts


def format_elements_for_context(elements: list[ParsedElement]) -> str:
    blocks: list[str] = []
    for element in elements:
        heading = f" [{element.heading}]" if element.heading else ""
        blocks.append(
            f"<{element.element_type}{heading} page={element.page_start}-{element.page_end}>\n{element.text.strip()}\n</{element.element_type}>"
        )
    return "\n\n".join(blocks).strip()
