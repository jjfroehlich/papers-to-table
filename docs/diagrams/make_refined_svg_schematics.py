from __future__ import annotations

import html
import math
import re
import textwrap
from pathlib import Path

import fitz


OUT_DIR = Path(__file__).resolve().parent / "refined_svg"


COLORS = {
    "ink": "#0f172a",
    "muted": "#617083",
    "soft_text": "#7b8798",
    "line": "#243247",
    "hairline": "#d9e2ec",
    "paper": "#f6f8fb",
    "surface": "#ffffff",
    "blue": "#2563eb",
    "blue_soft": "#eaf2ff",
    "teal": "#0f9f8f",
    "teal_soft": "#e6f7f3",
    "green": "#24a85b",
    "green_soft": "#e8f8ee",
    "orange": "#f08a24",
    "orange_soft": "#fff0dc",
    "purple": "#6d55e8",
    "purple_soft": "#efedff",
    "rose": "#e45670",
    "rose_soft": "#ffe8ed",
    "slate": "#334155",
    "slate_soft": "#eef3f8",
}


MARKER_KEYS = ["ink", "line", "blue", "teal", "green", "orange", "purple", "rose", "muted"]

SOFT_BY_ACCENT = {
    COLORS["blue"]: COLORS["blue_soft"],
    COLORS["teal"]: COLORS["teal_soft"],
    COLORS["green"]: COLORS["green_soft"],
    COLORS["orange"]: COLORS["orange_soft"],
    COLORS["purple"]: COLORS["purple_soft"],
    COLORS["rose"]: COLORS["rose_soft"],
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def wrap_text(value: str, max_width: float, font_size: float) -> list[str]:
    approx_chars = max(8, int(max_width / (font_size * 0.52)))
    lines: list[str] = []
    for paragraph in value.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=approx_chars, break_long_words=False))
    return lines


def soft_for(color: str) -> str:
    return SOFT_BY_ACCENT.get(color, COLORS["slate_soft"])


class SVG:
    def __init__(self, width: int, height: int, title: str):
        self.width = width
        self.height = height
        self.parts: list[str] = []
        self.parts.append(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
        )
        self.parts.append(f"<title>{esc(title)}</title>")
        self._defs()
        self.rect(0, 0, width, height, rx=0, fill=COLORS["paper"], stroke="none")

    def _defs(self) -> None:
        markers = []
        for key in MARKER_KEYS:
            color = COLORS[key]
            markers.append(
                f"""
  <marker id="arrow-{key}" viewBox="0 0 14 14" refX="12" refY="7" markerWidth="11" markerHeight="11" orient="auto-start-reverse">
    <path d="M 2 2 L 12 7 L 2 12 z" fill="{color}"/>
  </marker>"""
            )
        self.parts.append(
            """
<defs>
"""
            + "\n".join(markers)
            + "\n</defs>"
        )

    def raw(self, value: str) -> None:
        self.parts.append(value)

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        rx: float = 12,
        fill: str = COLORS["surface"],
        stroke: str = COLORS["hairline"],
        stroke_width: float = 2,
        opacity: float | None = None,
        dashed: bool = False,
        shadow: bool = False,
    ) -> None:
        if shadow:
            self.parts.append(
                f'<rect x="{x + 5:.1f}" y="{y + 7:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" '
                f'fill="#0f172a" opacity="0.055" stroke="none"/>'
            )
        attrs = []
        if opacity is not None:
            attrs.append(f'opacity="{opacity}"')
        if dashed:
            attrs.append('stroke-dasharray="9 8"')
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" {" ".join(attrs)}/>'
        )

    def circle(self, cx: float, cy: float, r: float, fill: str, stroke: str | None = None, stroke_width: float = 2) -> None:
        self.parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke or fill}" stroke-width="{stroke_width}"/>'
        )

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke: str = COLORS["line"],
        width: float = 3.5,
        dashed: bool = False,
        arrow: bool = False,
        marker: str = "line",
    ) -> None:
        dash = 'stroke-dasharray="10 9"' if dashed else ""
        marker_attr = ""
        if arrow:
            ux, uy = self._unit_vector(x1, y1, x2, y2)
            shorten = max(10.0, width * 3.1)
            x2_line = x2 - ux * shorten
            y2_line = y2 - uy * shorten
        else:
            x2_line = x2
            y2_line = y2
        self.parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2_line:.1f}" y2="{y2_line:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" {dash} {marker_attr}/>'
        )
        if arrow:
            self.arrowhead(x2, y2, x1, y1, COLORS.get(marker, stroke), size=max(11.0, width * 3.4))

    def path(
        self,
        d: str,
        stroke: str = COLORS["line"],
        width: float = 3.5,
        fill: str = "none",
        dashed: bool = False,
        arrow: bool = False,
        marker: str = "line",
    ) -> None:
        dash = 'stroke-dasharray="10 9"' if dashed else ""
        marker_attr = ""
        self.parts.append(
            f'<path d="{d}" stroke="{stroke}" stroke-width="{width}" fill="{fill}" '
            f'stroke-linecap="round" stroke-linejoin="round" {dash} {marker_attr}/>'
        )
        if arrow:
            points = self._path_points(d)
            if len(points) >= 2:
                x_prev, y_prev = points[-2]
                x_tip, y_tip = points[-1]
                self.arrowhead(x_tip, y_tip, x_prev, y_prev, COLORS.get(marker, stroke), size=max(11.0, width * 3.4))

    def _unit_vector(self, x1: float, y1: float, x2: float, y2: float) -> tuple[float, float]:
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy) or 1.0
        return dx / length, dy / length

    def _path_points(self, d: str) -> list[tuple[float, float]]:
        nums = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", d)]
        return list(zip(nums[0::2], nums[1::2]))

    def arrowhead(self, tip_x: float, tip_y: float, from_x: float, from_y: float, fill: str, size: float = 12.0) -> None:
        ux, uy = self._unit_vector(from_x, from_y, tip_x, tip_y)
        base_x = tip_x - ux * size
        base_y = tip_y - uy * size
        half = size * 0.46
        left_x = base_x + (-uy) * half
        left_y = base_y + ux * half
        right_x = base_x - (-uy) * half
        right_y = base_y - ux * half
        self.parts.append(
            f'<path d="M {tip_x:.1f} {tip_y:.1f} L {left_x:.1f} {left_y:.1f} L {right_x:.1f} {right_y:.1f} Z" '
            f'fill="{fill}" stroke="none"/>'
        )

    def text(
        self,
        x: float,
        y: float,
        value: str,
        size: float = 22,
        weight: int | str = 400,
        fill: str = COLORS["ink"],
        anchor: str = "start",
        max_width: float | None = None,
        line_height: float = 1.18,
        family: str = "Segoe UI, Inter, Arial, sans-serif",
    ) -> float:
        lines = [value] if max_width is None else wrap_text(value, max_width, size)
        font_weight = self._font_weight(weight)
        self.parts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
            f'font-weight="{font_weight}" fill="{fill}" text-anchor="{anchor}">'
        )
        for index, line in enumerate(lines):
            if index == 0:
                self.parts.append(f'<tspan x="{x:.1f}" dy="0">{esc(line)}</tspan>')
            else:
                self.parts.append(f'<tspan x="{x:.1f}" dy="{size * line_height:.1f}">{esc(line)}</tspan>')
        self.parts.append("</text>")
        return y + (len(lines) - 1) * size * line_height

    def _font_weight(self, weight: int | str) -> str:
        if isinstance(weight, int):
            return "bold" if weight >= 700 else "normal"
        if isinstance(weight, str) and weight.isdigit():
            return "bold" if int(weight) >= 700 else "normal"
        return weight

    def pill(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        label: str,
        fill: str,
        stroke: str,
        text_fill: str | None = None,
        size: float = 15,
        weight: int | str = 800,
    ) -> None:
        self.rect(x, y, w, h, rx=7, fill=fill, stroke=stroke, stroke_width=1.6)
        self.text(x + w / 2, y + h / 2 + size * 0.36, label, size=size, weight=weight, fill=text_fill or stroke, anchor="middle")

    def footer(self, label: str) -> None:
        return None

    def finish(self) -> str:
        self.parts.append("</svg>")
        return "\n".join(self.parts)


def heading(svg: SVG, title: str, subtitle: str) -> None:
    svg.text(42, 48, title, size=34, weight=860, fill=COLORS["ink"])
    svg.text(42, 82, subtitle, size=17.5, fill=COLORS["muted"], max_width=svg.width - 84)


def page_icon_base(
    svg: SVG,
    x: float,
    y: float,
    s: float,
    stroke: str,
    fill: str = "#ffffff",
    fold_fill: str = "#eef3f8",
    stroke_width: float = 2.2,
) -> tuple[float, float, float, float]:
    """Draw a centered document page with a true folded corner."""
    left = x + s * 0.21
    top = y + s * 0.13
    right = x + s * 0.79
    bottom = y + s * 0.81
    fold = s * 0.17
    fx = right - fold
    fy = top + fold
    svg.path(
        f"M {left:.1f} {top:.1f} H {fx:.1f} L {right:.1f} {fy:.1f} "
        f"V {bottom:.1f} H {left:.1f} Z",
        fill=fill,
        stroke=stroke,
        width=stroke_width,
    )
    svg.path(
        f"M {fx:.1f} {top:.1f} L {right:.1f} {fy:.1f} L {fx:.1f} {fy:.1f} Z",
        fill=fold_fill,
        stroke="none",
        width=0,
    )
    svg.path(
        f"M {fx:.1f} {top:.1f} L {right:.1f} {fy:.1f} M {fx:.1f} {top:.1f} V {fy:.1f} H {right:.1f}",
        fill="none",
        stroke=stroke,
        width=1.6,
    )
    return left, top, right, bottom


ICON_OFFSETS = {
    "table": (0.07, 0.07),
    "schema": (0.07, 0.08),
    "local": (0.05, 0.04),
    "evidence": (0.06, 0.05),
    "review": (0.04, 0.03),
    "model": (0.05, 0.04),
    "optimizer": (0.08, 0.08),
    "agent": (0.05, 0.04),
    "headless": (0.05, 0.04),
    "vision": (0.05, 0.06),
    "lock": (0.07, 0.03),
    "shield": (0.07, 0.00),
    "quote": (0.04, 0.02),
}


def draw_icon(svg: SVG, name: str, x: float, y: float, size: float, color: str) -> None:
    s = size
    dx, dy = ICON_OFFSETS.get(name, (0.0, 0.0))
    x += s * dx
    y += s * dy
    ink = COLORS["ink"]
    muted = "#9badbf"
    if name == "pdfs":
        for dx, dy, opacity in [(-0.08, -0.05, 0.55), (-0.02, 0.01, 0.72)]:
            left, top, right, bottom = page_icon_base(
                svg,
                x + s * dx,
                y + s * dy,
                s,
                muted,
                fill="#ffffff",
                stroke_width=1.7,
            )
            svg.rect(left + s * 0.10, bottom - s * 0.18, s * 0.30, s * 0.055, rx=2, fill=muted, stroke=muted, stroke_width=0, opacity=opacity)
        left, top, right, bottom = page_icon_base(svg, x + s * 0.05, y + s * 0.07, s, muted, stroke_width=2.0)
        svg.rect(left + s * 0.11, bottom - s * 0.19, s * 0.36, s * 0.09, rx=3, fill=color, stroke=color, stroke_width=0)
    elif name == "table":
        svg.rect(x + s * 0.04, y + s * 0.10, s * 0.78, s * 0.66, rx=5, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.rect(x + s * 0.04, y + s * 0.10, s * 0.78, s * 0.15, rx=5, fill=color, stroke=color, stroke_width=0)
        for i in range(1, 4):
            svg.line(x + s * (0.04 + 0.78 * i / 4), y + s * 0.10, x + s * (0.04 + 0.78 * i / 4), y + s * 0.76, stroke="#b9c6d3", width=1.4)
            svg.line(x + s * 0.04, y + s * (0.10 + 0.66 * i / 4), x + s * 0.82, y + s * (0.10 + 0.66 * i / 4), stroke="#b9c6d3", width=1.4)
    elif name == "schema":
        svg.rect(x + s * 0.08, y + s * 0.11, s * 0.70, s * 0.60, rx=6, fill="#ffffff", stroke=ink, stroke_width=2.2)
        for yy in [0.29, 0.44, 0.59]:
            svg.line(x + s * 0.23, y + s * yy, x + s * 0.62, y + s * yy, stroke=color, width=3.2)
    elif name == "config":
        svg.rect(x + s * 0.18, y + s * 0.20, s * 0.64, s * 0.56, rx=7, fill="#ffffff", stroke=ink, stroke_width=2.2)
        for yy, knob in [(0.34, 0.62), (0.49, 0.38), (0.64, 0.54)]:
            svg.line(x + s * 0.29, y + s * yy, x + s * 0.71, y + s * yy, stroke=color, width=3.0)
            svg.circle(x + s * knob, y + s * yy, s * 0.055, fill="#ffffff", stroke=ink, stroke_width=2.0)
    elif name == "local":
        svg.rect(x + s * 0.08, y + s * 0.18, s * 0.68, s * 0.48, rx=8, fill="#ffffff", stroke=ink, stroke_width=2.3)
        svg.line(x + s * 0.24, y + s * 0.34, x + s * 0.58, y + s * 0.34, stroke=color, width=3.5)
        svg.line(x + s * 0.24, y + s * 0.49, x + s * 0.53, y + s * 0.49, stroke=color, width=3.5)
        svg.circle(x + s * 0.72, y + s * 0.62, s * 0.08, fill=color, stroke=color)
    elif name == "evidence":
        svg.circle(x + s * 0.34, y + s * 0.34, s * 0.19, fill="#ffffff", stroke=ink, stroke_width=2.3)
        svg.line(x + s * 0.49, y + s * 0.49, x + s * 0.76, y + s * 0.76, stroke=ink, width=4.2)
        svg.line(x + s * 0.21, y + s * 0.34, x + s * 0.47, y + s * 0.34, stroke=color, width=3.5)
        svg.line(x + s * 0.34, y + s * 0.21, x + s * 0.34, y + s * 0.47, stroke=color, width=3.5)
    elif name == "proposal":
        left, top, right, bottom = page_icon_base(svg, x, y, s, ink)
        svg.line(left + s * 0.11, top + s * 0.27, right - s * 0.18, top + s * 0.27, stroke=muted, width=2.3)
        svg.rect(left + s * 0.11, top + s * 0.43, s * 0.34, s * 0.10, rx=4, fill=color, stroke=color, stroke_width=0)
        svg.circle(x + s * 0.72, y + s * 0.72, s * 0.14, fill="#ffffff", stroke=color, stroke_width=2.4)
        svg.path(f"M {x + s * 0.65:.1f} {y + s * 0.72:.1f} L {x + s * 0.71:.1f} {y + s * 0.78:.1f} L {x + s * 0.81:.1f} {y + s * 0.63:.1f}", stroke=color, width=3.0)
    elif name == "review":
        svg.rect(x + s * 0.08, y + s * 0.12, s * 0.66, s * 0.56, rx=6, fill="#ffffff", stroke=ink, stroke_width=2.2)
        for i, c in enumerate([COLORS["green"], COLORS["orange"], COLORS["rose"]]):
            yy = y + s * (0.27 + i * 0.14)
            svg.circle(x + s * 0.21, yy, s * 0.045, fill=c, stroke=c)
            svg.line(x + s * 0.30, yy, x + s * 0.62, yy, stroke="#b9c6d3", width=2.4)
        svg.circle(x + s * 0.72, y + s * 0.70, s * 0.14, fill=color, stroke=color)
    elif name == "export":
        left, top, right, bottom = page_icon_base(svg, x, y, s, ink)
        svg.line(left + s * 0.12, top + s * 0.34, right - s * 0.18, top + s * 0.34, stroke=color, width=3.2)
        svg.line(left + s * 0.12, top + s * 0.49, right - s * 0.25, top + s * 0.49, stroke=color, width=3.2)
        svg.circle(x + s * 0.72, y + s * 0.72, s * 0.14, fill="#ffffff", stroke=COLORS["green"], stroke_width=2.4)
        svg.path(f"M {x + s * 0.65:.1f} {y + s * 0.72:.1f} L {x + s * 0.71:.1f} {y + s * 0.78:.1f} L {x + s * 0.82:.1f} {y + s * 0.63:.1f}", stroke=COLORS["green"], width=3.0)
    elif name == "bundle":
        svg.path(
            f"M {x + s * 0.17:.1f} {y + s * 0.30:.1f} H {x + s * 0.38:.1f} "
            f"L {x + s * 0.46:.1f} {y + s * 0.39:.1f} H {x + s * 0.83:.1f} "
            f"V {y + s * 0.75:.1f} H {x + s * 0.17:.1f} Z",
            fill="#ffffff",
            stroke=ink,
            width=2.4,
        )
        svg.rect(x + s * 0.26, y + s * 0.47, s * 0.47, s * 0.10, rx=4, fill=color, stroke=color, stroke_width=0)
        svg.line(x + s * 0.30, y + s * 0.64, x + s * 0.66, y + s * 0.64, stroke=color, width=3.0)
        svg.circle(x + s * 0.74, y + s * 0.64, s * 0.045, fill=color, stroke=color)
    elif name == "model":
        svg.rect(x + s * 0.12, y + s * 0.14, s * 0.62, s * 0.52, rx=7, fill=ink, stroke=ink, stroke_width=2)
        for yy in [0.30, 0.44, 0.58]:
            svg.line(x + s * 0.26, y + s * yy, x + s * 0.59, y + s * yy, stroke=color, width=3.2)
        svg.circle(x + s * 0.72, y + s * 0.68, s * 0.07, fill=color, stroke=color)
    elif name == "optimizer":
        svg.circle(x + s * 0.42, y + s * 0.42, s * 0.25, fill="#ffffff", stroke=ink, stroke_width=2.2)
        for angle in range(0, 360, 60):
            a = math.radians(angle)
            svg.line(
                x + s * 0.42,
                y + s * 0.42,
                x + s * 0.42 + math.cos(a) * s * 0.18,
                y + s * 0.42 + math.sin(a) * s * 0.18,
                stroke=color,
                width=3.2,
            )
        svg.circle(x + s * 0.42, y + s * 0.42, s * 0.08, fill=color, stroke=color)
    elif name == "agent":
        svg.rect(x + s * 0.12, y + s * 0.16, s * 0.62, s * 0.46, rx=7, fill=ink, stroke=ink, stroke_width=2)
        svg.line(x + s * 0.25, y + s * 0.32, x + s * 0.58, y + s * 0.32, stroke=color, width=3.4)
        svg.line(x + s * 0.25, y + s * 0.48, x + s * 0.50, y + s * 0.48, stroke=color, width=3.4)
    elif name == "vision":
        svg.rect(x + s * 0.14, y + s * 0.18, s * 0.60, s * 0.42, rx=7, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.circle(x + s * 0.44, y + s * 0.39, s * 0.13, fill="#ffffff", stroke=color, stroke_width=2.5)
        svg.circle(x + s * 0.44, y + s * 0.39, s * 0.045, fill=color, stroke=color)
        svg.line(x + s * 0.17, y + s * 0.70, x + s * 0.72, y + s * 0.70, stroke=color, width=2.6)
    elif name == "benchmark":
        cx, cy = x + s * 0.50, y + s * 0.50
        svg.circle(cx, cy, s * 0.30, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.circle(cx, cy, s * 0.21, fill="none", stroke=color, stroke_width=3.2)
        svg.circle(cx, cy, s * 0.11, fill="none", stroke=ink, stroke_width=2.1)
        svg.circle(cx, cy, s * 0.045, fill=color, stroke=color)
        svg.line(cx - s * 0.36, cy, cx - s * 0.27, cy, stroke=color, width=2.6)
        svg.line(cx + s * 0.27, cy, cx + s * 0.36, cy, stroke=color, width=2.6)
        svg.line(cx, cy - s * 0.36, cx, cy - s * 0.27, stroke=color, width=2.6)
        svg.line(cx, cy + s * 0.27, cx, cy + s * 0.36, stroke=color, width=2.6)
    elif name == "report":
        svg.rect(x + s * 0.14, y + s * 0.18, s * 0.72, s * 0.58, rx=7, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.line(x + s * 0.14, y + s * 0.32, x + s * 0.86, y + s * 0.32, stroke=ink, width=1.8)
        for dx in [0.23, 0.31, 0.39]:
            svg.circle(x + s * dx, y + s * 0.25, s * 0.022, fill=color, stroke=color)
        baseline = y + s * 0.64
        for bx, h in [(0.43, 0.16), (0.50, 0.25), (0.57, 0.34)]:
            svg.rect(x + s * bx, baseline - s * h, s * 0.045, s * h, rx=1.5, fill=color, stroke=color, stroke_width=0)
        svg.line(x + s * 0.40, baseline, x + s * 0.64, baseline, stroke="#b9c6d3", width=1.6)
        svg.path(
            f"M {x + s * 0.34:.1f} {y + s * 0.48:.1f} L {x + s * 0.27:.1f} {y + s * 0.55:.1f} "
            f"L {x + s * 0.34:.1f} {y + s * 0.62:.1f} "
            f"M {x + s * 0.70:.1f} {y + s * 0.48:.1f} L {x + s * 0.77:.1f} {y + s * 0.55:.1f} "
            f"L {x + s * 0.70:.1f} {y + s * 0.62:.1f}",
            stroke=color,
            width=2.7,
        )
    elif name == "headless":
        svg.rect(x + s * 0.12, y + s * 0.18, s * 0.62, s * 0.46, rx=8, fill=ink, stroke=ink, stroke_width=2)
        svg.path(f"M {x + s * 0.25:.1f} {y + s * 0.33:.1f} L {x + s * 0.35:.1f} {y + s * 0.41:.1f} L {x + s * 0.25:.1f} {y + s * 0.49:.1f}", stroke=color, width=3.5)
        svg.line(x + s * 0.45, y + s * 0.50, x + s * 0.63, y + s * 0.50, stroke=color, width=3.5)
    elif name == "orchestrator":
        cx, cy = x + s * 0.50, y + s * 0.50
        nodes = [
            (x + s * 0.50, y + s * 0.18),
            (x + s * 0.80, y + s * 0.50),
            (x + s * 0.50, y + s * 0.82),
            (x + s * 0.20, y + s * 0.50),
        ]
        for nx, ny in nodes:
            svg.line(cx, cy, nx, ny, stroke=color, width=3.0)
        svg.circle(cx, cy, s * 0.15, fill="#ffffff", stroke=ink, stroke_width=2.4)
        svg.circle(cx, cy, s * 0.065, fill=color, stroke=color)
        for nx, ny in nodes:
            svg.circle(nx, ny, s * 0.065, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.path(
            f"M {x + s * 0.33:.1f} {y + s * 0.31:.1f} C {x + s * 0.46:.1f} {y + s * 0.19:.1f}, "
            f"{x + s * 0.64:.1f} {y + s * 0.21:.1f}, {x + s * 0.73:.1f} {y + s * 0.36:.1f}",
            stroke=ink,
            width=2.4,
        )
        svg.path(
            f"M {x + s * 0.72:.1f} {y + s * 0.28:.1f} L {x + s * 0.75:.1f} {y + s * 0.39:.1f} "
            f"L {x + s * 0.64:.1f} {y + s * 0.37:.1f}",
            stroke=ink,
            width=2.4,
        )
    elif name == "loop":
        cx, cy = x + s * 0.50, y + s * 0.50
        svg.path(
            f"M {x + s * 0.30:.1f} {y + s * 0.32:.1f} "
            f"C {x + s * 0.42:.1f} {y + s * 0.18:.1f}, {x + s * 0.67:.1f} {y + s * 0.20:.1f}, {x + s * 0.74:.1f} {y + s * 0.39:.1f}",
            stroke=ink,
            width=3.0,
        )
        svg.path(
            f"M {x + s * 0.70:.1f} {y + s * 0.30:.1f} L {x + s * 0.76:.1f} {y + s * 0.43:.1f} L {x + s * 0.62:.1f} {y + s * 0.42:.1f}",
            stroke=ink,
            width=3.0,
        )
        svg.path(
            f"M {x + s * 0.70:.1f} {y + s * 0.68:.1f} "
            f"C {x + s * 0.58:.1f} {y + s * 0.82:.1f}, {x + s * 0.33:.1f} {y + s * 0.80:.1f}, {x + s * 0.26:.1f} {y + s * 0.61:.1f}",
            stroke=color,
            width=3.0,
        )
        svg.path(
            f"M {x + s * 0.30:.1f} {y + s * 0.70:.1f} L {x + s * 0.24:.1f} {y + s * 0.57:.1f} L {x + s * 0.38:.1f} {y + s * 0.58:.1f}",
            stroke=color,
            width=3.0,
        )
        svg.circle(cx, cy, s * 0.13, fill="#ffffff", stroke=color, stroke_width=2.4)
        svg.circle(cx, cy, s * 0.045, fill=color, stroke=color)
    elif name == "eval":
        svg.rect(x + s * 0.10, y + s * 0.12, s * 0.56, s * 0.56, rx=6, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.line(x + s * 0.22, y + s * 0.30, x + s * 0.50, y + s * 0.30, stroke=color, width=3)
        svg.line(x + s * 0.22, y + s * 0.44, x + s * 0.46, y + s * 0.44, stroke=color, width=3)
        svg.line(x + s * 0.22, y + s * 0.58, x + s * 0.40, y + s * 0.58, stroke=color, width=3)
        svg.circle(x + s * 0.66, y + s * 0.64, s * 0.16, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.line(x + s * 0.78, y + s * 0.76, x + s * 0.88, y + s * 0.86, stroke=ink, width=3.6)
        svg.path(f"M {x + s * 0.58:.1f} {y + s * 0.64:.1f} L {x + s * 0.64:.1f} {y + s * 0.70:.1f} L {x + s * 0.75:.1f} {y + s * 0.56:.1f}", stroke=color, width=3)
    elif name == "skill-kit":
        svg.path(
            f"M {x + s * 0.24:.1f} {y + s * 0.18:.1f} H {x + s * 0.62:.1f} "
            f"V {y + s * 0.34:.1f} H {x + s * 0.76:.1f} V {y + s * 0.66:.1f} "
            f"H {x + s * 0.58:.1f} V {y + s * 0.78:.1f} H {x + s * 0.24:.1f} Z",
            fill="#ffffff",
            stroke=ink,
            width=2.4,
        )
        svg.line(x + s * 0.32, y + s * 0.36, x + s * 0.54, y + s * 0.36, stroke=color, width=3.2)
        svg.line(x + s * 0.32, y + s * 0.52, x + s * 0.66, y + s * 0.52, stroke=color, width=3.2)
        svg.line(x + s * 0.32, y + s * 0.68, x + s * 0.48, y + s * 0.68, stroke=color, width=3.2)
    elif name == "lock":
        svg.rect(x + s * 0.22, y + s * 0.38, s * 0.42, s * 0.32, rx=5, fill=color, stroke=color, stroke_width=0)
        svg.path(
            f"M {x + s * 0.30:.1f} {y + s * 0.38:.1f} L {x + s * 0.30:.1f} {y + s * 0.28:.1f} "
            f"C {x + s * 0.30:.1f} {y + s * 0.08:.1f}, {x + s * 0.56:.1f} {y + s * 0.08:.1f}, {x + s * 0.56:.1f} {y + s * 0.28:.1f} "
            f"L {x + s * 0.56:.1f} {y + s * 0.38:.1f}",
            stroke=ink,
            width=3.0,
        )
        svg.circle(x + s * 0.43, y + s * 0.54, s * 0.035, fill="#ffffff", stroke="#ffffff")
    elif name == "shield":
        svg.path(
            f"M {x + s * 0.43:.1f} {y + s * 0.08:.1f} L {x + s * 0.72:.1f} {y + s * 0.20:.1f} "
            f"L {x + s * 0.68:.1f} {y + s * 0.48:.1f} C {x + s * 0.64:.1f} {y + s * 0.66:.1f}, "
            f"{x + s * 0.52:.1f} {y + s * 0.76:.1f}, {x + s * 0.43:.1f} {y + s * 0.82:.1f} "
            f"C {x + s * 0.34:.1f} {y + s * 0.76:.1f}, {x + s * 0.22:.1f} {y + s * 0.66:.1f}, "
            f"{x + s * 0.18:.1f} {y + s * 0.48:.1f} L {x + s * 0.14:.1f} {y + s * 0.20:.1f} Z",
            fill=soft_for(color),
            stroke=ink,
            width=2.4,
        )
        svg.path(f"M {x + s * 0.31:.1f} {y + s * 0.45:.1f} L {x + s * 0.40:.1f} {y + s * 0.54:.1f} L {x + s * 0.58:.1f} {y + s * 0.34:.1f}", stroke=color, width=3.4)
    elif name == "user":
        svg.circle(x + s * 0.42, y + s * 0.26, s * 0.13, fill="#ffffff", stroke=ink, stroke_width=2.4)
        svg.path(
            f"M {x + s * 0.17:.1f} {y + s * 0.72:.1f} C {x + s * 0.21:.1f} {y + s * 0.51:.1f}, "
            f"{x + s * 0.31:.1f} {y + s * 0.44:.1f}, {x + s * 0.42:.1f} {y + s * 0.44:.1f} "
            f"C {x + s * 0.55:.1f} {y + s * 0.44:.1f}, {x + s * 0.64:.1f} {y + s * 0.51:.1f}, "
            f"{x + s * 0.67:.1f} {y + s * 0.72:.1f}",
            fill="none",
            stroke=ink,
            width=2.6,
        )
        svg.circle(x + s * 0.68, y + s * 0.62, s * 0.15, fill=color, stroke=color)
        svg.path(
            f"M {x + s * 0.60:.1f} {y + s * 0.62:.1f} L {x + s * 0.66:.1f} {y + s * 0.68:.1f} "
            f"L {x + s * 0.77:.1f} {y + s * 0.53:.1f}",
            stroke="#ffffff",
            width=3.0,
        )
    elif name == "spreadsheet":
        svg.rect(x + s * 0.10, y + s * 0.12, s * 0.66, s * 0.64, rx=5, fill="#ffffff", stroke=COLORS["green"], stroke_width=2.3)
        for i in [0.32, 0.52]:
            svg.line(x + s * 0.10, y + s * i, x + s * 0.76, y + s * i, stroke=COLORS["green"], width=2)
        for i in [0.32, 0.54]:
            svg.line(x + s * i, y + s * 0.12, x + s * i, y + s * 0.76, stroke=COLORS["green"], width=2)
        svg.circle(x + s * 0.74, y + s * 0.70, s * 0.14, fill=COLORS["green"], stroke=COLORS["green"])
        svg.path(f"M {x + s * 0.67:.1f} {y + s * 0.70:.1f} L {x + s * 0.73:.1f} {y + s * 0.76:.1f} L {x + s * 0.84:.1f} {y + s * 0.61:.1f}", stroke="#ffffff", width=3)
    elif name == "quote":
        svg.rect(x + s * 0.12, y + s * 0.18, s * 0.64, s * 0.46, rx=7, fill="#ffffff", stroke=ink, stroke_width=2.2)
        svg.path(f"M {x + s * 0.30:.1f} {y + s * 0.64:.1f} L {x + s * 0.22:.1f} {y + s * 0.78:.1f} L {x + s * 0.44:.1f} {y + s * 0.64:.1f}", fill="#ffffff", stroke=ink, width=2.2)
        svg.line(x + s * 0.24, y + s * 0.33, x + s * 0.36, y + s * 0.33, stroke=color, width=3.2)
        svg.line(x + s * 0.24, y + s * 0.47, x + s * 0.40, y + s * 0.47, stroke=color, width=3.2)
        svg.line(x + s * 0.50, y + s * 0.33, x + s * 0.62, y + s * 0.33, stroke=color, width=3.2)
        svg.line(x + s * 0.50, y + s * 0.47, x + s * 0.66, y + s * 0.47, stroke=color, width=3.2)
        svg.circle(x + s * 0.70, y + s * 0.62, s * 0.08, fill=color, stroke=color)
    elif name == "quote-marks":
        svg.path(
            f"M {x + s * 0.18:.1f} {y + s * 0.42:.1f} C {x + s * 0.18:.1f} {y + s * 0.28:.1f}, "
            f"{x + s * 0.31:.1f} {y + s * 0.22:.1f}, {x + s * 0.41:.1f} {y + s * 0.22:.1f} "
            f"L {x + s * 0.41:.1f} {y + s * 0.42:.1f} L {x + s * 0.28:.1f} {y + s * 0.42:.1f} "
            f"L {x + s * 0.28:.1f} {y + s * 0.58:.1f} L {x + s * 0.18:.1f} {y + s * 0.70:.1f}",
            stroke=color,
            width=3.2,
        )
        svg.path(
            f"M {x + s * 0.50:.1f} {y + s * 0.42:.1f} C {x + s * 0.50:.1f} {y + s * 0.28:.1f}, "
            f"{x + s * 0.63:.1f} {y + s * 0.22:.1f}, {x + s * 0.73:.1f} {y + s * 0.22:.1f} "
            f"L {x + s * 0.73:.1f} {y + s * 0.42:.1f} L {x + s * 0.60:.1f} {y + s * 0.42:.1f} "
            f"L {x + s * 0.60:.1f} {y + s * 0.58:.1f} L {x + s * 0.50:.1f} {y + s * 0.70:.1f}",
            stroke=color,
            width=3.2,
        )
    else:
        svg.circle(x + s * 0.42, y + s * 0.42, s * 0.30, fill=color, stroke=ink, stroke_width=2.2)


def panel(svg: SVG, x: float, y: float, w: float, h: float, title: str, accent: str, fill: str = COLORS["surface"], subtitle: str | None = None) -> None:
    svg.rect(x, y, w, h, rx=14, fill=fill, stroke=accent, stroke_width=2.2, opacity=0.92)
    svg.line(x + 18, y + 52, x + w - 18, y + 52, stroke=accent, width=2.4)
    svg.text(x + 22, y + 34, title, size=20, weight=850, fill=COLORS["ink"])
    if subtitle:
        svg.text(x + 22, y + 74, subtitle, size=13.5, fill=COLORS["muted"], max_width=w - 44)


def boundary(svg: SVG, x: float, y: float, w: float, h: float, label: str, accent: str, fill: str, note: str | None = None) -> None:
    svg.rect(x, y, w, h, rx=22, fill=fill, stroke=accent, stroke_width=2.4, opacity=0.70, dashed=True)
    label_w = max(190, len(label) * 9.2)
    svg.pill(x + 28, y - 17, label_w, 34, label, COLORS["surface"], accent, size=14.5)
    if note:
        svg.text(x + w - 24, y + h - 22, note, size=14, weight=750, fill=accent, anchor="end")


def number_badge(svg: SVG, cx: float, cy: float, n: str, color: str) -> None:
    svg.circle(cx, cy, 25, fill=color, stroke=COLORS["surface"], stroke_width=4)
    svg.text(cx, cy + 9, n, size=24, weight=900, fill="#ffffff", anchor="middle")


def action_node(svg: SVG, x: float, y: float, w: float, h: float, title: str, body: str, icon: str, color: str) -> None:
    svg.rect(x, y, w, h, rx=13, fill=COLORS["surface"], stroke=COLORS["hairline"], stroke_width=1.8, shadow=True)
    svg.rect(x, y, 6, h, rx=3, fill=color, stroke=color, stroke_width=0)
    icon_y = y + (h - 56) / 2
    svg.circle(x + 50, icon_y + 28, 34, fill=soft_for(color), stroke="#dce6f0", stroke_width=1.2)
    draw_icon(svg, icon, x + 22, icon_y, 56, color)
    title_bottom = svg.text(x + 88, y + 32, title, size=18, weight=850, max_width=w - 104)
    svg.text(x + 88, max(y + 57, title_bottom + 18), body, size=13.2, fill=COLORS["muted"], max_width=w - 104, line_height=1.08)


def artifact_node(svg: SVG, x: float, y: float, w: float, h: float, title: str, body: str, icon: str, color: str, fill: str = COLORS["surface"]) -> None:
    svg.rect(x, y, w, h, rx=11, fill=fill, stroke=color, stroke_width=2.3, shadow=True)
    icon_y = y + (h - 60) / 2
    svg.circle(x + 48, icon_y + 30, 36, fill=soft_for(color), stroke="#dce6f0", stroke_width=1.2)
    draw_icon(svg, icon, x + 18, icon_y, 60, color)
    title_bottom = svg.text(x + 90, y + 38, title, size=20, weight=880, max_width=w - 118)
    svg.text(x + 90, max(y + 66, title_bottom + 20), body, size=13.8, fill=COLORS["muted"], max_width=w - 118, line_height=1.08)


def compact_node(svg: SVG, x: float, y: float, w: float, h: float, title: str, body: str, icon: str, color: str, dashed: bool = False) -> None:
    svg.rect(x, y, w, h, rx=11, fill=COLORS["surface"], stroke=color, stroke_width=1.9, dashed=dashed, shadow=True)
    draw_icon(svg, icon, x + 13, y + 18, 42, color)
    title_bottom = svg.text(x + 64, y + 32, title, size=16.2, weight=850, max_width=w - 72)
    svg.text(x + 64, max(y + 56, title_bottom + 15), body, size=11.5, fill=COLORS["muted"], max_width=w - 72, line_height=1.05)


def callout(svg: SVG, x: float, y: float, w: float, label: str, text: str, accent: str) -> None:
    svg.rect(x, y, w, 54, rx=10, fill=COLORS["surface"], stroke=COLORS["hairline"], stroke_width=1.6)
    svg.text(x + 20, y + 34, label, size=17, weight=850, fill=accent)
    svg.text(x + 136, y + 34, text, size=15, fill=COLORS["muted"], max_width=w - 158)


def diagram_icon_library() -> str:
    svg = SVG(1460, 920, "Reusable icon library")
    heading(svg, "Diagram Icon Set", "Reusable symbols for report figures, grouped by the role they play in the schematics.")

    groups = [
        (
            "Inputs and configuration",
            COLORS["blue"],
            50,
            125,
            [("pdfs", "PDFs"), ("table", "Target table"), ("schema", "Schema"), ("config", "Candidate settings")],
        ),
        (
            "Local execution and artifacts",
            COLORS["teal"],
            770,
            125,
            [("local", "Local run"), ("model", "Local model"), ("proposal", "Proposal"), ("bundle", "Run bundle")],
        ),
        (
            "Review and accepted outputs",
            COLORS["green"],
            50,
            385,
            [("quote", "Evidence quote"), ("user", "Human review"), ("spreadsheet", "Spreadsheet export"), ("report", "HTML report")],
        ),
        (
            "Optimizer sweep, eval, benchmark",
            COLORS["orange"],
            770,
            385,
            [("config", "Candidate sweep"), ("eval", "Eval scoring"), ("benchmark", "Benchmark gold"), ("headless", "Headless run")],
        ),
        (
            "Agent-facing workflows",
            COLORS["green"],
            50,
            645,
            [("agent", "Agent skill"), ("skill-kit", "Portable kit"), ("review", "Static review"), ("export", "Portable output")],
        ),
        (
            "Trust and boundaries",
            COLORS["purple"],
            770,
            645,
            [("lock", "Local privacy"), ("shield", "Verified state"), ("evidence", "Search evidence"), ("export", "Audit export")],
        ),
    ]

    for title, accent, x, y, icons in groups:
        panel(svg, x, y, 640, 220, title, accent, fill="#fbfdff")
        for i, (name, label) in enumerate(icons):
            col = i % 2
            row = i // 2
            tx = x + 34 + col * 286
            ty = y + 76 + row * 70
            svg.circle(tx + 29, ty + 29, 31, fill=COLORS["slate_soft"], stroke="#dce6f0", stroke_width=1.3)
            draw_icon(svg, name, tx, ty, 58, accent)
            svg.text(tx + 70, ty + 35, label, size=15.2, weight=820, max_width=174)

    return svg.finish()


def diagram_readme_overview() -> str:
    svg = SVG(1600, 830, "README overview refined schematic")
    heading(
        svg,
        "papers-to-table",
        "Extract, verify, review, and export structured values from scientific PDFs.",
    )

    boundary(
        svg,
        390,
        190,
        610,
        430,
        "private local processing boundary",
        COLORS["teal"],
        COLORS["teal_soft"],
        "source PDFs stay untouched",
    )
    draw_icon(svg, "lock", 558, 206, 34, COLORS["teal"])

    artifact_node(svg, 90, 315, 250, 175, "Inputs", "PDFs, table schema, config", "pdfs", COLORS["blue"], fill="#fbfdff")
    action_node(svg, 450, 295, 235, 142, "Local run", "preflight, parser, local LM", "shield", COLORS["teal"])
    artifact_node(svg, 715, 295, 235, 142, "Proposals", "values, quotes, page refs", "quote", COLORS["purple"], fill="#fbfdff")
    action_node(svg, 1080, 315, 245, 175, "Human review", "accept, edit, reject, no data", "user", COLORS["orange"])
    artifact_node(svg, 1350, 315, 205, 175, "Accepted export", "XLSX plus audit files", "spreadsheet", COLORS["green"], fill="#fbfdff")

    for cx, cy, n, color in [
        (130, 315, "1", COLORS["blue"]),
        (490, 295, "2", COLORS["teal"]),
        (755, 295, "3", COLORS["purple"]),
        (1120, 315, "4", COLORS["orange"]),
        (1390, 315, "5", COLORS["green"]),
    ]:
        number_badge(svg, cx, cy, n, color)

    svg.line(340, 402, 440, 402, stroke=COLORS["line"], width=4, arrow=True, marker="line")
    svg.line(685, 366, 705, 366, stroke=COLORS["line"], width=4, arrow=True, marker="line")
    svg.line(950, 402, 1070, 402, stroke=COLORS["line"], width=4, arrow=True, marker="line")
    svg.line(1325, 402, 1340, 402, stroke=COLORS["line"], width=4, arrow=True, marker="line")

    svg.rect(462, 488, 476, 72, rx=10, fill=COLORS["surface"], stroke=COLORS["teal"], stroke_width=1.8)
    svg.text(700, 520, "Default provider path: local LM Studio.", size=17, weight=760, fill=COLORS["teal"], anchor="middle")
    svg.text(700, 548, "No source document mutation.", size=14.5, fill=COLORS["muted"], anchor="middle")

    svg.rect(130, 700, 1340, 88, rx=14, fill=COLORS["surface"], stroke=COLORS["hairline"], stroke_width=1.8, shadow=True)
    values = [
        (210, "local first", "shield", COLORS["teal"]),
        (520, "evidence backed", "quote", COLORS["purple"]),
        (850, "human decision", "user", COLORS["orange"]),
        (1185, "accepted only", "spreadsheet", COLORS["green"]),
    ]
    for i, (x, label, icon, color) in enumerate(values):
        draw_icon(svg, icon, x, 722, 52, color)
        svg.text(x + 68, 754, label, size=21, weight=850, fill=color)
        if i < len(values) - 1:
            svg.line(x + 240, 744, x + 286, 744, stroke=COLORS["hairline"], width=3)

    svg.footer("Refined 01 - README overview")
    return svg.finish()


def diagram_main_lifecycle() -> str:
    svg = SVG(1800, 1040, "Main app lifecycle refined schematic")
    heading(
        svg,
        "Main-App Run Lifecycle",
        "A configured batch becomes evidence-backed proposal records, then explicit review decisions drive export.",
    )

    lanes = [
        (70, 175, 320, 805, "Setup", COLORS["blue"], COLORS["blue_soft"]),
        (430, 175, 320, 805, "Document preparation", COLORS["teal"], COLORS["teal_soft"]),
        (790, 175, 650, 805, "Extraction engine", COLORS["purple"], COLORS["purple_soft"]),
        (1480, 175, 250, 805, "Review and export", COLORS["orange"], COLORS["orange_soft"]),
    ]
    for x, y, w, h, title, accent, fill in lanes:
        panel(svg, x, y, w, h, title, accent, fill=fill)

    # Main connectors first, so nodes sit cleanly above linework.
    svg.line(230, 390, 230, 450, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.line(230, 565, 230, 625, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.line(335, 687, 470, 687, stroke=COLORS["line"], width=4, arrow=True, marker="line")
    svg.line(590, 390, 590, 450, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.line(590, 565, 590, 625, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.path("M 705 687 L 770 687 L 770 292 L 840 292", stroke=COLORS["line"], width=4, arrow=True, marker="line")
    for y1, y2 in [(327, 372), (454, 499), (581, 626), (708, 753)]:
        svg.line(1042, y1, 1042, y2, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.path("M 1218 817 L 1460 817 L 1460 366 L 1498 366", stroke=COLORS["line"], width=4, arrow=True, marker="line")
    svg.line(1604, 420, 1604, 575, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")
    svg.line(1604, 692, 1604, 835, stroke=COLORS["line"], width=3.2, arrow=True, marker="line")

    # Optional branch rail.
    svg.line(1220, 288, 1260, 353, stroke=COLORS["orange"], width=2.8, dashed=True, arrow=True, marker="orange")
    svg.line(1220, 542, 1260, 542, stroke=COLORS["green"], width=2.8, dashed=True, arrow=True, marker="green")
    svg.line(1220, 816, 1260, 739, stroke=COLORS["rose"], width=2.8, dashed=True, arrow=True, marker="rose")
    svg.text(1262, 248, "optional side rail", size=15, weight=830, fill=COLORS["muted"])

    action_node(svg, 115, 285, 235, 105, "Config", "paths and overrides", "config", COLORS["blue"])
    action_node(svg, 115, 460, 235, 105, "Preflight", "inputs, parser, provider", "local", COLORS["blue"])
    artifact_node(svg, 115, 635, 235, 105, "Ready", "run bundle starts", "export", COLORS["blue"], fill="#fbfdff")

    action_node(svg, 475, 285, 230, 105, "Parse PDFs", "Docling or configured parser", "pdfs", COLORS["teal"])
    action_node(svg, 475, 460, 230, 105, "Metadata", "title, DOI, authors, year", "schema", COLORS["teal"])
    artifact_node(svg, 475, 635, 230, 105, "Match rows", "matched, ambiguous, missing", "table", COLORS["teal"], fill="#fbfdff")

    action_node(svg, 840, 250, 380, 77, "Retrieve evidence", "text, tables, captions, figures", "evidence", COLORS["purple"])
    action_node(svg, 840, 377, 380, 77, "Build prompt", "schema plus row context", "schema", COLORS["purple"])
    action_node(svg, 840, 504, 380, 77, "Local model call", "OpenAI-compatible LM Studio", "model", COLORS["purple"])
    action_node(svg, 840, 631, 380, 77, "Normalize output", "typed values and evidence refs", "proposal", COLORS["purple"])
    artifact_node(svg, 840, 758, 380, 90, "Persist records", "proposal and evidence JSONL", "bundle", COLORS["purple"], fill="#fbfdff")

    compact_node(svg, 1260, 330, 140, 84, "Rescue", "bounded extra context", "evidence", COLORS["orange"], dashed=True)
    compact_node(svg, 1260, 500, 140, 84, "Vision", "targeted figure review", "vision", COLORS["green"], dashed=True)
    compact_node(svg, 1260, 670, 140, 84, "Select", "candidate arbitration", "table", COLORS["rose"], dashed=True)

    action_node(svg, 1498, 315, 200, 105, "Review", "explicit decisions", "review", COLORS["orange"])
    artifact_node(svg, 1498, 575, 200, 117, "Accepted", "approved decisions", "proposal", COLORS["green"], fill="#fbfdff")
    artifact_node(svg, 1498, 835, 200, 117, "Export", "workbook plus audit", "export", COLORS["green"], fill="#fbfdff")

    svg.rect(505, 925, 870, 72, rx=12, fill=COLORS["surface"], stroke=COLORS["teal"], stroke_width=2.1, shadow=True)
    draw_icon(svg, "proposal", 536, 937, 54, COLORS["teal"])
    svg.text(610, 962, "Canonical proposal record per target cell", size=23, weight=880)
    svg.text(610, 988, "evidence | diagnostics | review state | provenance", size=15.5, weight=780, fill=COLORS["teal"])
    svg.line(1038, 848, 1038, 925, stroke=COLORS["teal"], width=3, arrow=True, marker="teal")

    svg.footer("Refined 02 - main-app lifecycle")
    return svg.finish()


def diagram_orchestrator_eval_benchmark() -> str:
    svg = SVG(1700, 740, "Optimizer candidate sweep schematic")
    heading(
        svg,
        "Optimizer Candidate Sweep",
        "Candidate settings are tried as a batch; each app run produces bundles, eval scores against gold, and reports rank the results.",
    )

    svg.rect(45, 135, 1390, 505, rx=18, fill=COLORS["blue_soft"], stroke=COLORS["blue"], stroke_width=2.4, shadow=True)
    svg.text(80, 180, "Candidate settings drive the sweep", size=28, weight=900)
    svg.text(80, 210, "The same run/eval pass is repeated for candidate x benchmark x replicate, then scored together.", size=17, fill=COLORS["muted"])
    svg.pill(1135, 164, 250, 32, "batch of candidates", COLORS["blue"], COLORS["blue"], text_fill="#ffffff", size=14)
    svg.pill(1135, 205, 250, 32, "rank after scoring", COLORS["surface"], COLORS["blue"], size=14)

    line = COLORS["line"]
    svg.line(335, 333, 385, 333, stroke=line, width=3.2, arrow=True, marker="line")
    svg.line(620, 333, 650, 333, stroke=line, width=3.2, arrow=True, marker="line")
    svg.line(885, 333, 915, 333, stroke=line, width=3.2, arrow=True, marker="line")
    svg.line(1155, 333, 1180, 333, stroke=line, width=3.2, arrow=True, marker="line")
    svg.line(1415, 333, 1450, 333, stroke=COLORS["orange"], width=3.2, arrow=True, marker="orange")
    svg.line(1040, 455, 1040, 400, stroke=line, width=2.9, arrow=True, marker="line")

    svg.rect(96, 246, 255, 126, rx=13, fill="#dfeaff", stroke="#b9d2ff", stroke_width=1.2)
    svg.rect(88, 258, 255, 126, rx=13, fill="#edf4ff", stroke="#c7dbff", stroke_width=1.2)
    action_node(svg, 80, 270, 255, 126, "Candidate settings", "model / prompt / retrieval variants", "config", COLORS["blue"])
    svg.pill(105, 420, 205, 31, "many candidate rows", COLORS["surface"], COLORS["blue"], size=14)

    action_node(svg, 395, 273, 225, 120, "Run main app", "headless eval-mode execution", "local", COLORS["teal"])
    artifact_node(svg, 660, 273, 225, 120, "Run bundles", "proposals, evidence, diagnostics", "bundle", COLORS["green"], fill="#fbfdff")
    action_node(svg, 925, 273, 230, 120, "Eval tool", "scores bundles against gold", "eval", COLORS["purple"])
    artifact_node(svg, 1180, 273, 235, 120, "Score results", "metrics per candidate", "table", COLORS["purple"], fill="#fbfdff")

    artifact_node(svg, 925, 455, 230, 100, "Benchmark + gold", "auxiliary eval input", "benchmark", COLORS["purple"], fill="#fbfdff")
    svg.pill(1212, 430, 170, 31, "rank + summarize", COLORS["surface"], COLORS["orange"], size=14)
    artifact_node(svg, 1460, 273, 220, 120, "HTML reports", "ranked results and caveats", "report", COLORS["orange"], fill="#fbfdff")
    return svg.finish()


def diagram_agent_skills() -> str:
    svg = SVG(1500, 340, "Agent skill workflows schematic")
    svg.text(28, 47, "Agent-facing workflows", size=29, weight=900)
    svg.text(430, 47, "two different skill concepts; only one depends on the installed local app", size=18, fill=COLORS["muted"])

    svg.rect(30, 92, 650, 205, rx=14, fill=COLORS["blue_soft"], stroke=COLORS["blue"], stroke_width=2.2, shadow=True)
    draw_icon(svg, "headless", 76, 157, 58, COLORS["blue"])
    svg.text(165, 152, "Local-app skill", size=29, weight=900)
    svg.pill(474, 124, 150, 31, "calls main app", COLORS["blue"], COLORS["blue"], text_fill="#ffffff", size=14)
    svg.text(165, 192, "Agent runs the installed app headlessly", size=17, fill=COLORS["muted"])
    svg.text(165, 236, "preflight -> headless --accept-all --export", size=16.5, weight=850, fill=COLORS["blue"])
    svg.text(165, 270, "outputs run bundle + workbook; values are auto-accepted, not human-reviewed", size=14, fill=COLORS["muted"], max_width=430)

    svg.rect(820, 92, 650, 205, rx=14, fill=COLORS["green_soft"], stroke=COLORS["green"], stroke_width=2.2, shadow=True)
    draw_icon(svg, "skill-kit", 866, 157, 58, COLORS["green"])
    svg.text(955, 152, "Portable agent kit", size=29, weight=900)
    svg.pill(1260, 124, 140, 31, "standalone", COLORS["green"], COLORS["green"], text_fill="#ffffff", size=14)
    svg.text(955, 192, "Standalone skill for other agent systems", size=17, fill=COLORS["muted"])
    svg.text(955, 236, "uses app principles, but is standalone", size=16.5, weight=850, fill=COLORS["green"])
    svg.text(955, 270, "no local app or LM Studio; optional static review package", size=14, fill=COLORS["muted"], max_width=430)

    return svg.finish()


DIAGRAMS = [
    ("00_icon_library", diagram_icon_library),
    ("01_readme_overview_refined", diagram_readme_overview),
    ("02_main_app_lifecycle_refined", diagram_main_lifecycle),
    ("03_orchestrator_eval_benchmark_refined", diagram_orchestrator_eval_benchmark),
    ("04_agent_skills_refined", diagram_agent_skills),
]


def render_png(svg_path: Path, png_path: Path) -> None:
    doc = fitz.open("svg", svg_path.read_bytes())
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    pix.save(png_path)
    doc.close()


def manifest() -> str:
    lines = [
        "# Refined SVG schematics",
        "",
        "Generated from `make_refined_svg_schematics.py` as canonical documentation figures.",
        "",
        "Figure style:",
        "",
        "- Frameless canvases with no slide footer, sized per schematic for insertion into reports or docs.",
        "- Neutral connector linework; arrowheads are explicit vector shapes for Illustrator compatibility.",
        "- Icons are custom SVG symbols drawn in a Lucide-style stroke system with centered backplate alignment.",
        "- Text uses standard `bold` / `normal` SVG weights so Illustrator preserves hierarchy better.",
        "",
        "Included:",
        "",
        "- `00_icon_library.svg` / `.png`: updated reusable icon set with revised report, benchmark, settings, bundle, and document icons.",
        "- `01_readme_overview_refined.svg` / `.png`: README-level workflow schematic.",
        "- `02_main_app_lifecycle_refined.svg` / `.png`: detailed main-app lifecycle schematic.",
        "- `03_orchestrator_eval_benchmark_refined.svg` / `.png`: candidate-settings-driven optimizer sweep with app runs, run bundles, eval scoring with gold data, score results, and HTML reports.",
        "- `04_agent_skills_refined.svg` / `.png`: compact two-box agent skill workflow figure.",
        "",
        "Icon basis:",
        "",
        "- Simple geometry, round caps/joins, consistent density, and restrained backplates.",
        "- Lucide is ISC-licensed; the design guide was used as the icon consistency reference rather than vendoring a full external icon package.",
        "",
        "Companion-tools semantics:",
        "",
        "- Optimizer sweeps over candidate settings: run the main app, collect run bundles, evaluate against benchmark/gold data, score each candidate, and emit HTML reports.",
        "- Eval is scoring-only: it can score optimizer-produced run bundles, ordinary run bundles, or external filled tables against gold data.",
        "- `papers-to-table-local-app` skill is app-backed: an agent uses the installed local app headlessly and may auto-accept/export values without human review.",
        "- `papers-to-table-agent-kit` is portable and standalone: it borrows the app's schema/evidence/review/export principles but does not require the local app or LM Studio.",
        "",
        "Intentionally omitted from this refined set:",
        "",
        "- Standalone run-bundle schematic: not needed for the current docs plan.",
        "- Review-workspace schematic: use a real review UI screenshot instead.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, builder in DIAGRAMS:
        svg_path = OUT_DIR / f"{name}.svg"
        png_path = OUT_DIR / f"{name}.png"
        svg_path.write_text(builder(), encoding="utf-8")
        render_png(svg_path, png_path)
    (OUT_DIR / "README.md").write_text(manifest(), encoding="utf-8")


if __name__ == "__main__":
    main()
