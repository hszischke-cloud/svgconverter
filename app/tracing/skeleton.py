"""Convert a 1-pixel-wide skeleton image into ordered polylines.

The skeleton (a boolean array where True marks centerline pixels) is treated
as an 8-connected graph. Pixels are classified by their neighbour count:

    * degree 1        -> endpoint   (a line tip)
    * degree 2        -> path pixel (the body of a stroke)
    * degree 3 or 4+  -> junction   (where strokes meet/cross)

We walk every edge of that graph exactly once, producing a list of polylines.
Each polyline is a list of ``(row, col)`` pixel coordinates. Pure loops with no
endpoints or junctions (e.g. a circle) are handled separately so they are not
missed.
"""

from __future__ import annotations

import numpy as np

# 8-connectivity neighbour offsets.
_OFFSETS = [(-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)]


def _build_adjacency(points):
    """Map each skeleton pixel to its list of 8-connected skeleton neighbours."""
    adj = {}
    for r, c in points:
        nbrs = []
        for dr, dc in _OFFSETS:
            p = (r + dr, c + dc)
            if p in points:
                nbrs.append(p)
        adj[(r, c)] = nbrs
    return adj


def skeleton_to_polylines(skel: np.ndarray):
    """Trace ``skel`` into a list of polylines (lists of ``(row, col)`` tuples)."""
    coords = np.argwhere(skel)
    if coords.size == 0:
        return []

    points = {(int(r), int(c)) for r, c in coords}
    adj = _build_adjacency(points)
    degree = {p: len(nbrs) for p, nbrs in adj.items()}
    node_set = {p for p in points if degree[p] != 2}

    visited_edges = set()
    polylines = []

    def edge(a, b):
        return (a, b) if a <= b else (b, a)

    def walk(start, first):
        """Walk from a node along path pixels until the next node or a dead end."""
        path = [start, first]
        visited_edges.add(edge(start, first))
        prev, cur = start, first
        while cur not in node_set:
            nxt = None
            for cand in adj[cur]:
                if cand == prev:
                    continue
                if edge(cur, cand) in visited_edges:
                    continue
                nxt = cand
                break
            if nxt is None:
                break
            visited_edges.add(edge(cur, nxt))
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    # Trace every edge that leaves a node (endpoints + junctions).
    for n in node_set:
        for nb in adj[n]:
            if edge(n, nb) not in visited_edges:
                polylines.append(walk(n, nb))

    # Anything left is an isolated loop (all pixels degree 2, no nodes).
    for p in points:
        for nb in adj[p]:
            if edge(p, nb) in visited_edges:
                continue
            path = [p, nb]
            visited_edges.add(edge(p, nb))
            prev, cur = p, nb
            while cur != p:
                nxt = None
                for cand in adj[cur]:
                    if cand == prev:
                        continue
                    if edge(cur, cand) in visited_edges:
                        continue
                    nxt = cand
                    break
                if nxt is None:
                    break
                visited_edges.add(edge(cur, nxt))
                path.append(nxt)
                prev, cur = cur, nxt
            polylines.append(path)

    return polylines
