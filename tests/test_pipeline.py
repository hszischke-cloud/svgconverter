"""Tests for the centerline tracing engine."""

import numpy as np
from PIL import Image

from app.tracing import TraceParams, trace
from app.tracing.bezier import catmull_rom_to_bezier, rdp
from app.tracing.skeleton import skeleton_to_polylines


def test_rdp_keeps_endpoints_and_drops_collinear():
    pts = [(0, 0), (1, 0.01), (2, 0), (3, 0)]
    out = rdp(pts, epsilon=0.5)
    assert out[0] == (0, 0)
    assert out[-1] == (3, 0)
    assert len(out) < len(pts)


def test_rdp_preserves_corner():
    pts = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
    out = rdp(pts, epsilon=0.5)
    assert (2, 0) in out  # the corner must survive


def test_catmull_rom_starts_with_moveto():
    d = catmull_rom_to_bezier([(0, 0), (1, 1), (2, 0), (3, 1)], tension=1.0)
    assert d.startswith("M 0 0")
    assert "C" in d


def test_catmull_rom_two_points_is_line():
    d = catmull_rom_to_bezier([(0, 0), (5, 5)])
    assert d == "M 0 0 L 5 5"


def test_skeleton_simple_line():
    skel = np.zeros((5, 10), dtype=bool)
    skel[2, 1:9] = True
    polylines = skeleton_to_polylines(skel)
    assert len(polylines) == 1
    # A horizontal line: 8 pixels traced end to end.
    assert len(polylines[0]) == 8


def test_skeleton_loop_has_no_endpoints():
    skel = np.zeros((7, 7), dtype=bool)
    skel[1, 1:6] = True
    skel[5, 1:6] = True
    skel[1:6, 1] = True
    skel[1:6, 5] = True
    polylines = skeleton_to_polylines(skel)
    assert len(polylines) >= 1
    total = sum(len(p) for p in polylines)
    assert total >= 16


def test_skeleton_empty():
    assert skeleton_to_polylines(np.zeros((4, 4), dtype=bool)) == []


def test_trace_produces_single_centerline_for_thick_line():
    # A thick horizontal bar (10px tall) should yield ONE centerline path,
    # not two outline paths. This is the core differentiator.
    arr = np.full((60, 120), 255, dtype=np.uint8)
    arr[25:35, 10:110] = 0  # thick black bar
    img = Image.fromarray(arr)

    result = trace(img, TraceParams(simplify=1.0, min_path_length=3))
    assert result.path_count == 1
    assert result.svg.count("<path") == 1
    # Estimated stroke width should be close to the 10px bar thickness.
    assert 6 <= result.stroke_width <= 14
    assert 'fill="none"' in result.svg
    assert "<svg" in result.svg


def test_trace_empty_image_is_safe():
    img = Image.fromarray(np.full((40, 40), 255, dtype=np.uint8))
    result = trace(img)
    assert result.path_count == 0
    assert "<svg" in result.svg
