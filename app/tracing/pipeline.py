"""End-to-end centerline tracing pipeline.

Takes a PIL image of clean line art and produces a centerline SVG: each drawn
stroke becomes a single vector running down the middle of the line, rather than
two outline vectors with a fill (which is what most tracers produce).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, label
from skimage.filters import threshold_otsu
from skimage.morphology import skeletonize

from .bezier import catmull_rom_to_bezier, rdp
from .skeleton import skeleton_to_polylines
from .svg import build_svg


@dataclass
class TraceParams:
    """Tunable knobs for the tracing pipeline."""

    threshold: Optional[int] = None      # 0-255, or None for automatic (Otsu)
    invert: bool = False                 # treat light lines on dark background
    min_object_size: int = 12            # remove speckles smaller than this (px)
    simplify: float = 1.5                # RDP tolerance in pixels
    smoothing: float = 1.0               # Catmull-Rom tension (0=straight, 1=smooth)
    min_path_length: int = 5             # drop polylines shorter than this (px)
    stroke_width: Optional[float] = None  # None -> auto-estimate from line weight
    stroke_color: str = "#1f3d1f"
    max_dimension: int = 2000            # downscale huge inputs for speed


@dataclass
class TraceResult:
    svg: str
    width: int
    height: int
    path_count: int
    stroke_width: float
    stats: dict = field(default_factory=dict)


def _to_mask(image: Image.Image, params: TraceParams) -> np.ndarray:
    """Convert an image to a boolean mask where True marks line pixels."""
    gray = np.asarray(image.convert("L"), dtype=np.uint8)

    if params.threshold is None:
        # Otsu picks the split between dark ink and light paper automatically.
        thr = threshold_otsu(gray) if gray.min() != gray.max() else 128
    else:
        thr = int(params.threshold)

    # Lines are assumed darker than the background. Use <= so degenerate
    # thresholds (e.g. Otsu returning 0 on extreme bimodal images) still match.
    mask = gray <= thr
    if params.invert:
        mask = ~mask
    return mask


def _despeckle(mask: np.ndarray, min_size: int) -> np.ndarray:
    """Drop connected components (8-connectivity) smaller than ``min_size`` px."""
    if min_size <= 0 or not mask.any():
        return mask
    structure = np.ones((3, 3), dtype=int)
    labels, count = label(mask, structure=structure)
    if count == 0:
        return mask
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0  # background label
    keep = sizes >= min_size
    return keep[labels]


def _estimate_stroke_width(mask: np.ndarray, skel: np.ndarray) -> float:
    """Estimate original line weight from the distance transform of the mask."""
    if not mask.any() or not skel.any():
        return 1.0
    dist = distance_transform_edt(mask)
    radii = dist[skel]
    radii = radii[radii > 0]
    if radii.size == 0:
        return 1.0
    # Diameter ~= 2 * median radius at the centerline.
    return float(max(1.0, round(2.0 * np.median(radii), 2)))


def trace(image: Image.Image, params: TraceParams | None = None) -> TraceResult:
    params = params or TraceParams()

    # Downscale very large images to keep tracing responsive.
    scale = 1.0
    w, h = image.size
    longest = max(w, h)
    if longest > params.max_dimension:
        scale = params.max_dimension / longest
        image = image.resize(
            (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
        )

    mask = _to_mask(image, params)
    mask = _despeckle(mask, params.min_object_size)

    skel = skeletonize(mask)
    polylines = skeleton_to_polylines(skel)

    stroke_w = (
        params.stroke_width
        if params.stroke_width is not None
        else _estimate_stroke_width(mask, skel)
    )

    path_data: List[str] = []
    kept = 0
    for pl in polylines:
        if len(pl) < params.min_path_length:
            continue
        # Skeleton coords are (row, col); SVG wants (x=col, y=row).
        pts = [(float(c), float(r)) for r, c in pl]
        pts = rdp(pts, params.simplify)
        if len(pts) < 2:
            continue
        path_data.append(catmull_rom_to_bezier(pts, params.smoothing))
        kept += 1

    height, width = mask.shape
    svg = build_svg(
        path_data,
        width=width,
        height=height,
        stroke_width=stroke_w,
        stroke_color=params.stroke_color,
    )

    return TraceResult(
        svg=svg,
        width=width,
        height=height,
        path_count=kept,
        stroke_width=stroke_w,
        stats={
            "raw_polylines": len(polylines),
            "kept_paths": kept,
            "skeleton_pixels": int(skel.sum()),
            "scale": round(scale, 4),
        },
    )
