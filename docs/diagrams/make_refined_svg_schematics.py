from __future__ import annotations

import hashlib
import html
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "refined_svg"

COLORS = {
    "paper": "#F7F8FA",
    "surface": "#FFFFFF",
    "ink": "#102033",
    "muted": "#5F6F82",
    "line": "#AAB6C4",
    "border": "#D9E0E8",
    "blue": "#2563EB",
    "blue_soft": "#EAF1FF",
    "teal": "#078B83",
    "teal_soft": "#E5F6F3",
    "green": "#168A4B",
    "green_soft": "#E8F6ED",
    "amber": "#D97706",
    "amber_soft": "#FFF3DE",
    "slate_soft": "#EEF2F6",
}

FONT = "Inter, Segoe UI, Arial, sans-serif"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def wrap(value: str, width: float, size: float) -> list[str]:
    chars = max(7, int(width / (size * 0.54)))
    return textwrap.wrap(value, width=chars, break_long_words=False) or [""]


class SVG:
    def __init__(self, width: int, height: int, title: str, description: str):
        self.width = width
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{esc(title)}</title>',
            f'<desc id="desc">{esc(description)}</desc>',
            "<defs>",
            '<filter id="shadow" x="-15%" y="-20%" width="140%" height="155%">'
            '<feDropShadow dx="0" dy="5" stdDeviation="6" flood-color="#102033" flood-opacity="0.08"/>'
            "</filter>",
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="{COLORS["paper"]}"/>',
        ]

    def raw(self, value: str) -> None:
        self.parts.append(value)

    def rect(self, x: float, y: float, w: float, h: float, *, fill: str = COLORS["surface"],
             stroke: str = COLORS["border"], sw: float = 1.5, rx: float = 14,
             shadow: bool = False, dashed: bool = False) -> None:
        attrs = []
        if shadow:
            attrs.append('filter="url(#shadow)"')
        if dashed:
            attrs.append('stroke-dasharray="7 7"')
        self.raw(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}" {" ".join(attrs)}/>' )

    def circle(self, x: float, y: float, r: float, *, fill: str, stroke: str = "none", sw: float = 1.5) -> None:
        self.raw(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')

    def text(self, x: float, y: float, value: str, *, size: float = 16, weight: int = 400,
             fill: str = COLORS["ink"], anchor: str = "start", max_width: float | None = None,
             line_height: float = 1.2) -> int:
        lines = wrap(value, max_width, size) if max_width else value.split("\n")
        self.raw(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
                 f'fill="{fill}" text-anchor="{anchor}">')
        for i, line in enumerate(lines):
            dy = 0 if i == 0 else size * line_height
            self.raw(f'<tspan x="{x}" dy="{dy}">{esc(line)}</tspan>')
        self.raw("</text>")
        return len(lines)

    def line(self, x1: float, y1: float, x2: float, y2: float, *, color: str = COLORS["line"],
             sw: float = 2.5, arrow: bool = False, dashed: bool = False) -> None:
        dash = 'stroke-dasharray="7 7"' if dashed else ""
        end_x, end_y = x2, y2
        if arrow:
            dx, dy = x2 - x1, y2 - y1
            length = max((dx * dx + dy * dy) ** 0.5, 1)
            end_x, end_y = x2 - dx / length * 12, y2 - dy / length * 12
        self.raw(f'<line x1="{x1}" y1="{y1}" x2="{end_x}" y2="{end_y}" stroke="{color}" '
                 f'stroke-width="{sw}" stroke-linecap="round" {dash}/>' )
        if arrow:
            self.arrow(x2, y2, x1, y1, color)

    def path(self, d: str, *, color: str = COLORS["line"], sw: float = 2.5,
             dashed: bool = False) -> None:
        dash = 'stroke-dasharray="7 7"' if dashed else ""
        self.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linecap="round" stroke-linejoin="round" {dash}/>' )

    def arrow(self, x: float, y: float, from_x: float, from_y: float, color: str) -> None:
        dx, dy = x - from_x, y - from_y
        length = max((dx * dx + dy * dy) ** 0.5, 1)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        bx, by = x - ux * 13, y - uy * 13
        self.raw(f'<path d="M {x} {y} L {bx + px * 6} {by + py * 6} L {bx - px * 6} {by - py * 6} Z" fill="{color}"/>')

    def finish(self) -> str:
        return "\n".join(self.parts + ["</svg>", ""])


def heading(s: SVG, title: str, subtitle: str = "") -> None:
    s.text(48, 52, title, size=32, weight=700)


def icon(s: SVG, name: str, x: float, y: float, color: str, scale: float = 1.0) -> None:
    """Small consistent 24-unit line icons, centered at x/y."""
    sw = 2.2 * scale
    def p(d: str, c: str = color) -> None:
        s.raw(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>')
    def l(x1: float, y1: float, x2: float, y2: float, c: str = color) -> None:
        s.line(x + x1 * scale, y + y1 * scale, x + x2 * scale, y + y2 * scale, color=c, sw=sw)
    if name in {"pdf", "file", "bundle", "export"}:
        p(f'M {x-8*scale} {y-11*scale} H {x+3*scale} L {x+9*scale} {y-5*scale} V {y+11*scale} H {x-8*scale} Z')
        l(-4, 3, 5, 3); l(-4, 7, 3, 7)
        if name == "export":
            l(-2, -3, 5, -3, COLORS["green"]); l(5, -3, 2, -6, COLORS["green"]); l(5, -3, 2, 0, COLORS["green"])
    elif name in {"table", "schema"}:
        s.rect(x-10*scale, y-9*scale, 20*scale, 18*scale, fill="none", stroke=color, sw=sw, rx=2*scale)
        l(-10, -3, 10, -3); l(-3, -9, -3, 9); l(4, -9, 4, 9); l(-10, 3, 10, 3)
    elif name in {"local", "model", "terminal"}:
        s.rect(x-11*scale, y-8*scale, 22*scale, 16*scale, fill="none", stroke=color, sw=sw, rx=3*scale)
        l(-7, -2, -3, 1); l(-3, 1, -7, 4); l(0, 4, 6, 4)
    elif name in {"evidence", "search", "eval"}:
        s.circle(x-2*scale, y-2*scale, 7*scale, fill="none", stroke=color, sw=sw)
        l(3, 3, 10, 10)
        if name == "evidence":
            l(-6, -2, 2, -2); l(-2, -6, -2, 2)
    elif name in {"review", "person"}:
        s.circle(x, y-6*scale, 4*scale, fill="none", stroke=color, sw=sw)
        p(f'M {x-8*scale} {y+10*scale} C {x-7*scale} {y+2*scale}, {x+7*scale} {y+2*scale}, {x+8*scale} {y+10*scale}')
    elif name in {"check", "accepted"}:
        s.circle(x, y, 10*scale, fill="none", stroke=color, sw=sw)
        p(f'M {x-5*scale} {y} L {x-1*scale} {y+4*scale} L {x+6*scale} {y-5*scale}')
    elif name in {"settings", "sliders"}:
        for yy, knob in [(-7, -3), (0, 4), (7, -5)]:
            l(-10, yy, 10, yy)
            s.circle(x+knob*scale, y+yy*scale, 2.2*scale, fill=COLORS["surface"], stroke=color, sw=sw)
    elif name == "loop":
        p(f'M {x-8*scale} {y-2*scale} A {9*scale} {9*scale} 0 0 1 {x+6*scale} {y-7*scale} L {x+9*scale} {y-7*scale} L {x+9*scale} {y-11*scale}')
        p(f'M {x+8*scale} {y+2*scale} A {9*scale} {9*scale} 0 0 1 {x-6*scale} {y+7*scale} L {x-9*scale} {y+7*scale} L {x-9*scale} {y+11*scale}')
    elif name == "report":
        s.rect(x-11*scale, y-9*scale, 22*scale, 18*scale, fill="none", stroke=color, sw=sw, rx=2*scale)
        l(-6, 5, -6, 0); l(0, 5, 0, -5); l(6, 5, 6, -1)
    else:
        s.circle(x, y, 9*scale, fill="none", stroke=color, sw=sw)


def icon_badge(s: SVG, x: float, y: float, name: str, color: str, soft: str, size: float = 46) -> None:
    s.circle(x, y, size/2, fill=soft)
    icon(s, name, x, y, color, scale=size/52)


def card(s: SVG, x: float, y: float, w: float, h: float, title: str, body: str,
         name: str, color: str, soft: str, *, step: str | None = None) -> None:
    s.rect(x, y, w, h, shadow=True)
    s.rect(x, y, 6, h, fill=color, stroke=color, sw=0, rx=3)
    icon_badge(s, x+39, y+h/2, name, color, soft)
    title_lines = s.text(x+76, y+37, title, size=18, weight=700, max_width=w-92)
    body_y = y + 65 + (title_lines - 1) * 21.6
    s.text(x+76, body_y, body, size=14, fill=COLORS["muted"], max_width=w-92)
    if step:
        s.circle(x+17, y-10, 18, fill=color, stroke=COLORS["paper"], sw=3)
        s.text(x+17, y-4, step, size=14, weight=700, fill="#FFFFFF", anchor="middle")


def pill(s: SVG, x: float, y: float, w: float, label: str, color: str, soft: str) -> None:
    s.rect(x, y, w, 30, fill=soft, stroke="none", sw=0, rx=15)
    s.text(x+w/2, y+20, label, size=13, weight=700, fill=color, anchor="middle")


def diagram_icon_library() -> str:
    s = SVG(1280, 760, "Diagram icon library v2", "Reusable normalized vector icons grouped by semantic role.")
    heading(s, "Diagram icon system", "A compact, consistent symbol set for the v2 documentation schematics.")
    groups = [
        ("Inputs", COLORS["blue"], COLORS["blue_soft"], [("PDF", "pdf"), ("Table", "table"), ("Schema", "schema"), ("Settings", "settings")]),
        ("Processing", COLORS["teal"], COLORS["teal_soft"], [("Local app", "local"), ("Model", "model"), ("Loop", "loop"), ("Search", "search")]),
        ("Evidence & review", COLORS["amber"], COLORS["amber_soft"], [("Evidence", "evidence"), ("Review", "review"), ("Accepted", "accepted"), ("Eval", "eval")]),
        ("Artifacts & tools", COLORS["green"], COLORS["green_soft"], [("Bundle", "bundle"), ("Export", "export"), ("Report", "report"), ("Terminal", "terminal")]),
    ]
    for gi, (title, color, soft, items) in enumerate(groups):
        x = 48 + (gi % 2) * 608
        y = 124 + (gi // 2) * 294
        s.rect(x, y, 560, 250, shadow=False)
        s.text(x+24, y+34, title, size=17, weight=700, fill=color)
        for i, (label, name) in enumerate(items):
            ix = x+72+(i%4)*134
            iy = y+112
            icon_badge(s, ix, iy, name, color, soft, 58)
            s.text(ix, iy+60, label, size=14, weight=600, anchor="middle")
            s.text(ix, iy+83, "24 px / 2.2", size=12, fill=COLORS["muted"], anchor="middle")
    return s.finish()


def diagram_readme() -> str:
    s = SVG(1440, 650, "papers-to-table overview v2", "Five-step local-first workflow from source inputs through accepted-only export.")
    heading(s, "papers-to-table", "Extract source-linked values from scientific PDFs, review every decision, and export an audited workbook.")
    y, w, h, gap = 205, 238, 138, 38
    nodes = [
        ("Inputs", "PDFs, table, schema, config", "pdf", COLORS["blue"], COLORS["blue_soft"]),
        ("Local processing", "preflight, parse, retrieve", "local", COLORS["teal"], COLORS["teal_soft"]),
        ("Cell proposals", "value, quote, page reference", "evidence", COLORS["blue"], COLORS["blue_soft"]),
        ("Human review", "accept, edit, reject, no data", "review", COLORS["amber"], COLORS["amber_soft"]),
        ("Accepted export", "new XLSX plus audit artifacts", "export", COLORS["green"], COLORS["green_soft"]),
    ]
    xs = [38+i*(w+gap) for i in range(5)]
    s.rect(xs[1]-18, 150, w*2+gap+36, 248, fill=COLORS["teal_soft"], stroke=COLORS["teal"], sw=1.5, rx=20, dashed=True)
    pill(s, xs[1]+68, 136, 378, "PRIVATE LOCAL PROCESSING · LM STUDIO DEFAULT", COLORS["teal"], COLORS["surface"])
    for i, ((title, body, name, color, soft), x) in enumerate(zip(nodes, xs), 1):
        card(s, x, y, w, h, title, body, name, color, soft, step=str(i))
        if i < 5:
            s.line(x+w, y+h/2, xs[i]-8, y+h/2, color=COLORS["line"], arrow=True)
    principles = [
        ("Everything stays local", "Documents and processing remain on your machine.", COLORS["teal"], COLORS["teal_soft"], "local"),
        ("Sources included", "Every proposal includes its source and evidence.", COLORS["blue"], COLORS["blue_soft"], "evidence"),
        ("Human-reviewed export", "Only human-reviewed values are exported.", COLORS["green"], COLORS["green_soft"], "accepted"),
    ]
    for i, (title, body, color, soft, name) in enumerate(principles):
        x = 148+i*390
        s.rect(x, 470, 356, 104, shadow=False)
        icon_badge(s, x+42, 522, name, color, soft, 44)
        s.text(x+76, 510, title, size=16, weight=700, fill=color)
        s.text(x+76, 536, body, size=13.5, fill=COLORS["muted"], max_width=252)
    return s.finish()


def diagram_readme_user_overview() -> str:
    s = SVG(1440, 620, "Simple evidence trail overview v2", "A continuous source-to-table evidence trail through local proposal generation and human review.")

    # Minimal stage labels.
    for x, label, color in [(176, "Source", COLORS["blue"]), (446, "Local LLM", COLORS["teal"]), (690, "Proposal", COLORS["blue"]), (944, "Review (optional)", COLORS["line"]), (1232, "Table", COLORS["green"])]:
        s.text(x, 72, label, size=20, weight=700, fill=COLORS["ink"], anchor="middle")
        s.line(x-20, 88, x+20, 88, color=color, sw=2)

    # Source: a paper stack with a magnifier over one highlighted sentence.
    for x, y in [(34, 160), (46, 148), (58, 136)]:
        s.rect(x, y, 250, 350, fill=COLORS["surface"], stroke=COLORS["border"], sw=1.2, rx=7, shadow=True)
    s.text(183, 178, "RESEARCH ARTICLE", size=10.5, weight=700, fill=COLORS["muted"], anchor="middle")
    for yy, ww in [(204, 174), (226, 190), (248, 158), (356, 184), (378, 150), (414, 178), (436, 126)]:
        s.rect(88, yy, ww, 6, fill=COLORS["slate_soft"], stroke="none", sw=0, rx=3)
    s.text(84, 282, "We discovered that PE efficiency in", size=12, weight=400)
    s.text(84, 306, "HEK293T cells was much higher than", size=12, weight=400)
    s.text(84, 330, "previously observed,", size=12, weight=400)
    s.rect(80, 340, 210, 52, fill=COLORS["amber_soft"], stroke="none", sw=0, rx=4)
    s.text(84, 361, "reaching up to 95%", size=12, weight=400)
    s.text(84, 384, "(mean 67%).", size=12, weight=400)

    # Neutral flow line keeps color emphasis on meaning, not connectors.
    s.path("M 286 366 C 340 366, 354 338, 386 338 C 486 338, 500 338, 548 338 C 650 338, 768 338, 856 352 S 1002 388, 1064 388 C 1130 388, 1190 388, 1300 388", color=COLORS["line"], sw=2.5)
    for cx, cy in [(286, 366), (386, 338), (548, 338), (856, 352), (1064, 388), (1300, 388)]:
        s.circle(cx, cy, 6, fill=COLORS["surface"], stroke=COLORS["line"], sw=2)

    # Local processing occupies the transition from source to proposal.
    s.circle(446, 338, 60, fill=COLORS["teal_soft"], stroke=COLORS["teal"], sw=1.4)
    icon(s, "local", 446, 312, COLORS["teal"], 1.45)
    s.text(446, 354, "retrieve · extract", size=11, weight=600, fill=COLORS["teal"], anchor="middle")
    s.text(446, 374, "local · LM Studio", size=10, fill=COLORS["muted"], anchor="middle")

    # Proposal: one large value with its source attached.
    s.rect(558, 176, 294, 340, fill=COLORS["surface"], stroke=COLORS["border"], sw=1.4, rx=14, shadow=True)
    s.text(584, 210, "FIELD", size=10.5, weight=600, fill=COLORS["muted"])
    s.text(584, 236, "Max editing efficiency", size=17, weight=600)
    s.line(584, 254, 826, 254, color=COLORS["border"], sw=1)
    s.text(584, 280, "PROPOSED VALUE", size=10.5, weight=600, fill=COLORS["muted"])
    s.text(584, 326, "95%", size=38, weight=700, fill=COLORS["blue"])
    s.rect(580, 352, 250, 138, fill=COLORS["slate_soft"], stroke="none", sw=0, rx=10)
    s.text(596, 376, "EVIDENCE", size=10.5, weight=600, fill=COLORS["muted"])
    s.text(596, 401, "“PE efficiency … reaching up to", size=12, weight=400, fill=COLORS["muted"])
    s.text(596, 422, "95% (mean 67%).”", size=12, weight=400, fill=COLORS["muted"])
    s.text(596, 452, "p. 10785 · Abstract · lines 4–6", size=10.5, weight=400, fill=COLORS["muted"])
    s.text(596, 472, "GE02_optimized_prime_editing_cells.pdf", size=10.5, weight=400, fill=COLORS["muted"])

    # Review: simplified human checkpoint, visually centered on the evidence line.
    s.circle(944, 330, 68, fill=COLORS["slate_soft"], stroke="none", sw=0)
    icon(s, "review", 934, 320, COLORS["ink"], 1.35)
    s.circle(970, 354, 18, fill=COLORS["green_soft"], stroke=COLORS["surface"], sw=3)
    icon(s, "check", 970, 354, COLORS["green"], .58)
    s.text(944, 424, "human decision or skip", size=12, weight=600, fill=COLORS["muted"], anchor="middle")

    # Table: the accepted value glows in its destination cell.
    tx, ty, tw, th = 1064, 174, 340, 306
    s.rect(tx, ty, tw, th, fill=COLORS["surface"], stroke=COLORS["green"], sw=1.5, rx=12, shadow=True)
    s.rect(tx, ty, tw, 45, fill=COLORS["ink"], stroke="none", sw=0, rx=12)
    cols = [tx, tx+94, tx+174, tx+252, tx+tw]
    for xx in cols[1:-1]:
        s.line(xx, ty, xx, ty+th, color=COLORS["border"], sw=1)
    for yy in [ty+45, ty+97, ty+149, ty+201, ty+253]:
        s.line(tx, yy, tx+tw, yy, color=COLORS["border"], sw=1)
    s.text(tx+10, ty+28, "Paper", size=10.5, weight=700, fill="#FFFFFF")
    s.text(tx+102, ty+20, "Editing", size=9.5, weight=700, fill="#FFFFFF")
    s.text(tx+102, ty+34, "modality", size=9.5, weight=700, fill="#FFFFFF")
    s.text(tx+182, ty+20, "Primary", size=9.5, weight=700, fill="#FFFFFF")
    s.text(tx+182, ty+34, "assay", size=9.5, weight=700, fill="#FFFFFF")
    s.text(tx+260, ty+20, "Max editing", size=9.2, weight=700, fill="#FFFFFF")
    s.text(tx+260, ty+34, "efficiency", size=9.2, weight=700, fill="#FFFFFF")
    target_y = ty + 151
    s.rect(tx+253, target_y, 86, 49, fill=COLORS["green_soft"], stroke=COLORS["green"], sw=1.5, rx=5)
    s.text(tx+10, target_y+24, "Adikusuma", size=10.2, weight=700)
    s.text(tx+10, target_y+39, "et al. (2021)", size=9.3, weight=600)
    s.text(tx+102, target_y+30, "prime editing", size=9.5, weight=600)
    s.text(tx+182, target_y+24, "HEK293T", size=9.2, weight=600)
    s.text(tx+182, target_y+39, "cells", size=9.2, weight=600)
    s.text(tx+279, target_y+32, "95%", size=17, weight=700, fill=COLORS["green"])
    for row_y in [ty+72, ty+124, ty+228, ty+280]:
        for xx, ww in [(tx+12, 54), (tx+105, 42), (tx+184, 42), (tx+274, 38)]:
            s.rect(xx, row_y, ww, 6, fill=COLORS["slate_soft"], stroke="none", sw=0, rx=3)
    pill(s, 1138, 500, 192, "ACCEPTED VALUES ONLY", COLORS["green"], COLORS["green_soft"])
    return s.finish()


def lane(s: SVG, x: float, y: float, w: float, h: float, title: str, color: str, soft: str) -> None:
    s.rect(x, y, w, h, fill=soft, stroke=COLORS["border"], sw=1.3, rx=18)
    s.text(x+22, y+34, title, size=17, weight=700, fill=color)
    s.line(x+20, y+48, x+w-20, y+48, color=color, sw=2)


def diagram_lifecycle() -> str:
    s = SVG(1640, 980, "Main-app details v2", "Four-lane lifecycle from setup through extraction, explicit review, and accepted-only export.")
    heading(s, "Main-app details")
    top, height = 128, 788
    specs = [(42,270,"1  Setup",COLORS["blue"],COLORS["blue_soft"]),(330,270,"2  Prepare documents",COLORS["teal"],COLORS["teal_soft"]),(618,626,"3  Extract proposals",COLORS["blue"],COLORS["blue_soft"]),(1262,336,"4  Review & export",COLORS["amber"],COLORS["amber_soft"])]
    for x,w,title,color,soft in specs: lane(s,x,top,w,height,title,color,soft)
    # setup and preparation
    for x, items, color, soft in [
        (68, [("Config", "paths and overrides", "settings"),("Preflight", "inputs, parser, provider", "check"),("Ready", "run bundle starts", "bundle")], COLORS["blue"], COLORS["blue_soft"]),
        (356, [("Parse PDFs", "configured parser", "pdf"),("Metadata", "title, DOI, authors, year", "schema"),("Match rows", "matched, ambiguous, missing", "table")], COLORS["teal"], COLORS["teal_soft"]),
    ]:
        for i,(title,body,name) in enumerate(items):
            y=222+i*188
            card(s,x,y,218,104,title,body,name,color,soft)
            if i<2: s.line(x+109,y+104,x+109,y+176,color=COLORS["line"],arrow=True)
    s.line(286, 650, 346, 650, color=COLORS["line"], arrow=True)
    # extraction primary rail
    primary=[("Retrieve evidence","text, tables, captions, figures","evidence"),("Build prompt","schema plus row context","schema"),("Local model call","validated structured output","model"),("Normalize & persist","one proposal record per cell","bundle")]
    for i,(title,body,name) in enumerate(primary):
        y=204+i*156
        card(s,650,y,344,98,title,body,name,COLORS["blue"],COLORS["blue_soft"])
        if i<3:s.line(822,y+98,822,y+146,color=COLORS["line"],arrow=True)
    s.path("M 574 650 H 610 V 253 H 640", color=COLORS["line"], sw=2.5)
    s.arrow(650,253,610,253,COLORS["line"])
    # optional rail
    opts=[("Recall rescue","extra context","search",COLORS["amber"],COLORS["amber_soft"]),("Figure review","targeted vision","evidence",COLORS["teal"],COLORS["teal_soft"]),("Candidate select","one arbitration","table",COLORS["amber"],COLORS["amber_soft"])]
    opt_ys = [201, 513, 669]
    for (title,body,name,color,soft), y in zip(opts, opt_ys):
        s.rect(1038,y,158,104,shadow=False)
        icon_badge(s,1066,y+52,name,color,soft,38)
        s.text(1092,y+42,title,size=14,weight=700,max_width=92)
        s.text(1092,y+75,body,size=12.5,fill=COLORS["muted"],max_width=92)
        s.line(994, y+52, 1028, y+52, color=color, sw=2, arrow=True, dashed=True)
    # proposal handoff and review
    s.rect(668,822,528,64,fill=COLORS["surface"],stroke=COLORS["teal"],sw=1.5,rx=12)
    s.text(692,848,"CANONICAL HANDOFF",size=12,weight=700,fill=COLORS["teal"])
    s.text(692,872,"value · evidence · diagnostics · review state · provenance",size=14,weight=600)
    s.line(822,770,822,812,color=COLORS["teal"],arrow=True)
    review=[("Review proposals","explicit human decisions","review",COLORS["amber"],COLORS["amber_soft"]),("Accepted decisions","accepted or accepted with edit","accepted",COLORS["green"],COLORS["green_soft"]),("Export copy","workbook plus audit artifacts","export",COLORS["green"],COLORS["green_soft"])]
    for i,(title,body,name,color,soft) in enumerate(review):
        y=232+i*208
        card(s,1290,y,280,112,title,body,name,color,soft)
        if i<2:s.line(1430,y+112,1430,y+196,color=COLORS["line"],arrow=True)
    s.path("M 1196 854 H 1238 V 288 H 1280",color=COLORS["line"],sw=2.5)
    s.arrow(1290,288,1238,288,COLORS["line"])
    pill(s,1322,814,214,"ACCEPTED CHANGES ONLY",COLORS["green"],COLORS["green_soft"])
    return s.finish()


def diagram_optimizer() -> str:
    s=SVG(1500,760,"Optimizer tool v2","Repeated candidate by benchmark by replicate studies produce persisted bundles, Eval scores, aggregates, and reports.")
    heading(s,"Optimizer tool")
    s.rect(44,126,1070,568,fill=COLORS["blue_soft"],stroke=COLORS["blue"],sw=1.5,rx=20)
    icon_badge(s, 98, 163, "loop", COLORS["blue"], COLORS["surface"], 38)
    pill(s,124,148,354,"REPEAT: CANDIDATE × BENCHMARK × REPLICATE",COLORS["blue"],COLORS["surface"])
    sequence=[("Candidate settings","model, prompt, retrieval","settings",COLORS["blue"],COLORS["blue_soft"]),("Main-app run","headless eval mode","local",COLORS["teal"],COLORS["teal_soft"]),("Persisted run bundle","proposals, evidence, diagnostics","bundle",COLORS["teal"],COLORS["teal_soft"]),("Eval scoring","gold comparison + judges","eval",COLORS["blue"],COLORS["blue_soft"]),("Per-run result","metrics and caveats","table",COLORS["blue"],COLORS["blue_soft"])]
    xs=[72,278,492,720,930]
    widths=[174,184,196,184,154]
    for i,((title,body,name,color,soft),x,w) in enumerate(zip(sequence,xs,widths)):
        card(s,x,270,w,150,title,body,name,color,soft)
        if i<4:s.line(x+w,345,xs[i+1]-10,345,color=COLORS["line"],arrow=True)
    inputs=[("Benchmark","masked inputs and gold answers","table"),("Judge A","independent LLM judge","eval"),("Judge B","independent LLM judge","eval")]
    for i,(title,body,name) in enumerate(inputs):
        x=566+i*170
        s.rect(x,500,152,98,shadow=False)
        icon_badge(s,x+28,549,name,COLORS["blue"],COLORS["surface"],38)
        s.text(x+52,535,title,size=13.5,weight=700,max_width=92)
        s.text(x+52,562,body,size=11.5,fill=COLORS["muted"],max_width=92)
        target_x = 796 + i * 16
        s.path(f"M {x+76} 500 V 458 H {target_x} V 432", color=COLORS["line"], sw=2)
        s.arrow(target_x, 420, target_x, 458, COLORS["line"])
    # aggregation outside repeat boundary
    s.line(1114,345,1160,345,color=COLORS["amber"],arrow=True)
    card(s,1170,236,286,150,"Aggregate study","combine and rank candidates across completed runs","report",COLORS["amber"],COLORS["amber_soft"])
    s.line(1313,386,1313,442,color=COLORS["line"],arrow=True)
    card(s,1170,452,286,150,"HTML reports","recommendations, plots, caveats","report",COLORS["green"],COLORS["green_soft"])
    pill(s,1196,620,234,"AFTER ALL RUNS COMPLETE",COLORS["amber"],COLORS["amber_soft"])
    return s.finish()


def diagram_agents() -> str:
    s=SVG(1440,390,"Agent skills v2","Minimal comparison of the local-app and agent-kit skills.")
    heading(s,"Agent skills")
    entries = [
        (48, '"local-app"', "Uses the locally installed papers-to-table app with LM Studio", "creates run bundle + accepted export", "terminal", COLORS["blue"], COLORS["blue_soft"]),
        (744, '"agent-kit"', "Standalone and portable; works with cloud-based agents such as Codex and Claude", "adds an interface for human review", "bundle", COLORS["green"], COLORS["green_soft"]),
    ]
    for x, title, body, outcome, name, color, soft in entries:
        s.rect(x,104,648,220,fill=soft,stroke=color,sw=1.6,rx=18,shadow=True)
        icon_badge(s,x+62,214,name,color,COLORS["surface"],54)
        s.text(x+112,165,title,size=27,weight=700)
        s.text(x+112,207,body,size=16,fill=COLORS["muted"],max_width=470)
        s.text(x+112,270,outcome,size=16,weight=700,fill=color,max_width=470)
    return s.finish()


FIGURES = [
    ("00_icon_library", diagram_icon_library),
    ("01_readme_overview_refined", diagram_readme),
    ("01_readme_user_overview_refined", diagram_readme_user_overview),
    ("02_main_app_lifecycle_refined", diagram_lifecycle),
    ("03_orchestrator_eval_benchmark_refined", diagram_optimizer),
    ("04_agent_skills_refined", diagram_agents),
]


README = """# Refined SVG schematics

Generated by `docs/diagrams/make_refined_svg_schematics.py`. This is the canonical diagram source and output set used by the README and MkDocs manual.

## Included figures

- `00_icon_library`: normalized icons grouped by semantic role.
- `01_readme_overview_refined`: concise technical workflow for the MkDocs home page.
- `01_readme_user_overview_refined`: example-driven overview for first-time README visitors.
- `02_main_app_lifecycle_refined`: four-lane main-app lifecycle with an optional bounded-processing rail.
- `03_orchestrator_eval_benchmark_refined`: candidate × benchmark × replicate orchestration, persisted run bundles, Eval inputs, aggregation, and reporting.
- `04_agent_skills_refined`: aligned comparison of the app-backed and standalone agent workflows.

Each figure is emitted as editable SVG and a high-resolution PNG preview.

## Visual system

- Off-white canvas and white surfaces with restrained borders and shadows.
- Dark navy text; blue for core system flow, teal for local processing, green for accepted outputs, and amber for human decisions or study aggregation.
- Standard font fallback: Inter, Segoe UI, Arial, sans-serif.
- Consistent card radius, spacing, icon optical size, connector weight, and body text sizing.
- Neutral primary connectors; dashed colored connectors indicate optional bounded processing.

## Accessibility and portability

SVGs contain descriptive `<title>` and `<desc>` elements, use `role="img"` with `aria-labelledby`, draw explicit vector arrowheads, and reference no external images, fonts, scripts, or stylesheets.

## Semantic boundaries

- The main app is local-first by default and never mutates source workbooks in place.
- Export includes accepted changes only.
- Optimizer orchestrates; the main app extracts; Eval scores persisted outputs.
- The local-app skill depends on the installed app. The portable agent kit does not require the app or LM Studio.

## Regeneration

From the repository root:

```bash
python docs/diagrams/make_refined_svg_schematics.py
```

The generator validates XML structure, accessible labeling, view boxes, unique IDs, and absence of external resource references after writing the figures.
"""


def render_png(svg_path: Path, png_path: Path) -> None:
    doc = fitz.open("svg", svg_path.read_bytes())
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(png_path)
    doc.close()


def validate_svg(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    if root.attrib.get("viewBox") != f"0 0 {root.attrib.get('width')} {root.attrib.get('height')}":
        raise ValueError(f"invalid viewBox: {path}")
    ids = [node.attrib["id"] for node in root.iter() if "id" in node.attrib]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate SVG ids: {path}")
    if not any(node.tag.endswith("title") for node in root.iter()) or not any(node.tag.endswith("desc") for node in root.iter()):
        raise ValueError(f"missing title/desc: {path}")
    forbidden = ["http://", "https://", "<image", "<script", "@import"]
    body = text.replace('xmlns="http://www.w3.org/2000/svg"', "")
    if any(token in body for token in forbidden):
        raise ValueError(f"external or executable resource found: {path}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hashes: list[str] = []
    for name, builder in FIGURES:
        svg_path = OUT_DIR / f"{name}.svg"
        png_path = OUT_DIR / f"{name}.png"
        payload = builder()
        svg_path.write_text(payload, encoding="utf-8", newline="\n")
        validate_svg(svg_path)
        render_png(svg_path, png_path)
        hashes.append(f"{name}: {hashlib.sha256(payload.encode()).hexdigest()[:12]}")
    (OUT_DIR / "README.md").write_text(README, encoding="utf-8", newline="\n")
    print(f"Generated and validated {len(FIGURES)} SVG/PNG pairs in {OUT_DIR}")
    print("\n".join(hashes))


if __name__ == "__main__":
    main()
