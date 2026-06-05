"""Tests for the pen-plotter vector reordering engine."""

import math

from app.plotter import (
    _parse_subpaths,
    _reverse_segments,
    _segments_to_d,
    _travel,
    optimize_svg,
)


def _wrap(body: str, w=100, h=100) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{body}</svg>'
    )


# --- path parsing --------------------------------------------------------- #
def test_parse_simple_line():
    subs = _parse_subpaths("M 0 0 L 10 0")
    assert len(subs) == 1
    assert subs[0]["start"] == (0.0, 0.0)
    assert subs[0]["end"] == (10.0, 0.0)
    assert not subs[0]["closed"]


def test_parse_multiple_subpaths():
    subs = _parse_subpaths("M0 0 L5 0 M 20 20 L 25 20")
    assert len(subs) == 2
    assert subs[1]["start"] == (20.0, 20.0)


def test_parse_relative_and_shorthand():
    # m relative move, h/v shorthand expand to absolute lineto.
    subs = _parse_subpaths("m 10 10 h 10 v 10")
    assert len(subs) == 1
    assert subs[0]["start"] == (10.0, 10.0)
    assert subs[0]["end"] == (20.0, 20.0)


def test_parse_closed_path():
    subs = _parse_subpaths("M 0 0 L 10 0 L 10 10 Z")
    assert subs[0]["closed"]
    assert subs[0]["end"] == (0.0, 0.0)


# --- reversal ------------------------------------------------------------- #
def test_reverse_line():
    new_start, segs = _reverse_segments((0.0, 0.0), [("L", (10.0, 5.0))])
    assert new_start == (10.0, 5.0)
    assert segs == [("L", (0.0, 0.0))]


def test_reverse_cubic_swaps_controls():
    new_start, segs = _reverse_segments(
        (0.0, 0.0), [("C", (1.0, 2.0, 3.0, 4.0, 10.0, 0.0))]
    )
    assert new_start == (10.0, 0.0)
    # Controls swapped, target is the original start.
    assert segs == [("C", (3.0, 4.0, 1.0, 2.0, 0.0, 0.0))]


def test_reverse_roundtrip_d_endpoints():
    d = "M 0 0 C 1 2 3 4 10 0"
    sub = _parse_subpaths(d)[0]
    new_start, segs = _reverse_segments(sub["start"], sub["segments"])
    reparsed = _parse_subpaths(_segments_to_d(new_start, segs, False))[0]
    assert reparsed["start"] == (10.0, 0.0)
    assert reparsed["end"] == (0.0, 0.0)


# --- optimization --------------------------------------------------------- #
def test_optimize_reduces_travel():
    # Three short segments laid out so file order zig-zags badly.
    body = (
        '<path d="M 0 0 L 5 0" stroke="#000"/>'
        '<path d="M 90 0 L 95 0" stroke="#000"/>'
        '<path d="M 10 0 L 15 0" stroke="#000"/>'
    )
    result = optimize_svg(_wrap(body), group_by_color=False)
    assert result.path_count == 3
    assert result.optimized_travel <= result.original_travel
    assert result.optimized_travel < result.original_travel  # this layout improves


def test_optimize_reversal_picks_closer_end():
    # Second stroke is "backwards"; reversing it should beat not reversing.
    body = (
        '<path d="M 0 0 L 10 0" stroke="#000"/>'
        '<path d="M 30 0 L 11 0" stroke="#000"/>'
    )
    rev = optimize_svg(_wrap(body), allow_reverse=True, two_opt=False)
    norev = optimize_svg(_wrap(body), allow_reverse=False, two_opt=False)
    assert rev.optimized_travel < norev.optimized_travel


def test_optimize_preserves_stroke_count_and_dims():
    body = (
        '<polyline points="0,0 5,5 10,0" stroke="#f00"/>'
        '<line x1="50" y1="50" x2="60" y2="60" stroke="#00f"/>'
        '<rect x="20" y="20" width="10" height="10" stroke="#000"/>'
    )
    result = optimize_svg(_wrap(body, 200, 150))
    assert result.path_count == 3
    assert result.width == 200
    assert result.height == 150
    assert result.svg.count("<path") == 3


def test_optimize_group_by_color_keeps_colors_contiguous():
    body = (
        '<path d="M 0 0 L 1 0" stroke="red"/>'
        '<path d="M 50 0 L 51 0" stroke="blue"/>'
        '<path d="M 2 0 L 3 0" stroke="red"/>'
    )
    result = optimize_svg(_wrap(body), group_by_color=True)
    # Find the order of colors as emitted.
    colors = [
        line.split('stroke="')[1].split('"')[0]
        for line in result.svg.splitlines()
        if "<path" in line
    ]
    # All reds come before blue (or all blues before reds) - contiguous groups.
    first_blue = colors.index("blue")
    assert "red" not in colors[first_blue:]


def test_optimize_empty_svg_is_safe():
    result = optimize_svg(_wrap(""))
    assert result.path_count == 0
    assert result.optimized_travel == 0.0


def test_optimize_invalid_svg_raises():
    import pytest

    with pytest.raises(ValueError):
        optimize_svg("not <<< valid xml")


def test_travel_matches_manual_computation():
    # One stroke from (0,0)->(10,0); pen starts at origin so travel == 0.
    body = '<path d="M 0 0 L 10 0" stroke="#000"/>'
    result = optimize_svg(_wrap(body))
    assert math.isclose(result.optimized_travel, 0.0, abs_tol=1e-6)
