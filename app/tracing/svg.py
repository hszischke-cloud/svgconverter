"""Assemble traced paths into an SVG document."""

from __future__ import annotations

from typing import List


def build_svg(
    path_data: List[str],
    width: int,
    height: int,
    stroke_width: float,
    stroke_color: str = "#1f3d1f",
    background: str | None = None,
) -> str:
    """Combine path ``d`` strings into a single stroked SVG document.

    Every path is rendered with ``fill="none"`` and a shared stroke, so each
    drawn line becomes one centerline vector rather than a filled outline.
    """
    sw = f"{stroke_width:.2f}".rstrip("0").rstrip(".")
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    ]
    if background:
        lines.append(f'<rect width="{width}" height="{height}" fill="{background}"/>')

    lines.append(
        f'<g fill="none" stroke="{stroke_color}" stroke-width="{sw}" '
        f'stroke-linecap="round" stroke-linejoin="round">'
    )
    for d in path_data:
        if d:
            lines.append(f'<path d="{d}"/>')
    lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines)
