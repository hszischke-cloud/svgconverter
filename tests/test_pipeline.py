"""Tests for the centerline tracing engine."""

import numpy as np
from PIL import Image

from app.tracing import TraceParams, trace
from app.tracing.bezier import catmull_rom_to_bezier, rdp
from app.tracing.skeleton import skeleton_to_polylines, skeleton_to_strokes


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


def test_strokes_link_straight_line_through_crossing():
    # A long horizontal line crossed by a short vertical one. The raw tracer
    # splits this into 4 edges at the centre; linking should recover the
    # straight horizontal line as ONE stroke (2 strokes total).
    skel = np.zeros((21, 41), dtype=bool)
    skel[10, 1:40] = True   # horizontal
    skel[1:20, 20] = True   # vertical
    raw = skeleton_to_polylines(skel)
    strokes = skeleton_to_strokes(skel, max_bend=75, spur_length=0)
    assert len(raw) >= 4
    assert len(strokes) == 2  # one horizontal + one vertical, each unbroken
    longest = max(strokes, key=len)
    assert len(longest) >= 38  # spans nearly the full width


def test_strokes_prune_spur():
    # A line with a tiny barb sticking off it should drop the barb.
    skel = np.zeros((15, 30), dtype=bool)
    skel[7, 1:29] = True    # main line
    skel[5:7, 15] = True    # 2px spur
    strokes = skeleton_to_strokes(skel, max_bend=75, spur_length=5)
    # Only the main line survives.
    assert len(strokes) == 1
    assert len(strokes[0]) >= 27


def test_strokes_sharp_corner_not_merged_when_strict():
    # A right-angle L: with a strict bend limit the corner stays two strokes;
    # with a loose limit it links into one bending stroke.
    skel = np.zeros((25, 25), dtype=bool)
    skel[12, 2:13] = True   # horizontal arm into the corner (12,12)
    skel[2:13, 12] = True   # vertical arm into the corner
    strict = skeleton_to_strokes(skel, max_bend=30, spur_length=0)
    loose = skeleton_to_strokes(skel, max_bend=120, spur_length=0)
    assert len(strict) == 2
    assert len(loose) == 1


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
