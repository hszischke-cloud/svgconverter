# Centerline SVG Converter

A web app that converts images of line art into SVGs using **centerline tracing**.

## What makes it different

Most image-to-SVG converters (Potrace and nearly every online tool) trace the
**outline** of a stroke. A line drawn 6 pixels wide comes out as *two* parallel
vectors with a fill between them — so a single pen stroke becomes a closed,
filled shape.

This tool traces the **centerline** instead: it thins each stroke down to its
1-pixel skeleton and emits **one** vector running down the middle, rendered as a
stroked path. One drawn line in → one centerline vector out.

```
Outline tracer:            Centerline tracer (this app):

  ┌──────────────┐
  │              │  fill           ──────────────────   single stroked path
  └──────────────┘
  (2 vectors + fill)          (1 vector, stroke-width set to match)
```

## How it works

The tracing engine (`app/tracing/`) runs this pipeline:

1. **Grayscale + binarize** — Otsu thresholding separates dark ink from light
   paper (with an invert toggle and manual threshold override).
2. **Despeckle** — small connected components are removed.
3. **Skeletonize** — `skimage.morphology.skeletonize` reduces every stroke to a
   1-pixel-wide centerline.
4. **Graph trace** — skeleton pixels are classified by neighbour count into
   endpoints / junctions / path pixels, then walked into ordered polylines
   (`skeleton.py`). Closed loops with no endpoints are handled explicitly.
5. **Stroke linking** — junction pixels are clustered, dead-end spurs pruned,
   and edges meeting at a junction are paired by **tangent continuity**: the
   two whose directions are most collinear are merged into one stroke that
   *bends* through the junction. This keeps a line that crosses or touches
   other lines as a single vector instead of fragmenting into many pieces, so
   the output uses far fewer paths.
6. **Simplify** — Ramer–Douglas–Peucker drops redundant points (`bezier.py`).
7. **Smooth** — polylines become smooth cubic Bézier curves via a Catmull-Rom
   spline conversion.
8. **Stroke width** — estimated from the distance transform of the mask so the
   SVG stroke roughly matches the original line weight.
9. **Emit** — each path is written as `<path fill="none" stroke=... />`
   (`svg.py`).

## Running it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open <http://localhost:8000>. Drop in an image, tweak the options, preview
the result side-by-side, and download the SVG.

### Options

| Option        | What it does                                                        |
|---------------|---------------------------------------------------------------------|
| Threshold     | Ink/paper cutoff (0–255), or **auto** (Otsu).                       |
| Invert        | For light lines on a dark background.                               |
| Line merging  | Max bend angle (deg) to keep a line continuing through a junction. Higher = fewer, more-bending vectors. |
| Prune spurs   | Remove dead-end barbs (skeleton noise) shorter than this many px.   |
| Smoothing     | Curve tension: 0 = straight segments, 1 = smooth spline.            |
| Simplify      | RDP tolerance in pixels — higher = fewer, looser points.            |
| Despeckle     | Minimum connected-component size to keep (removes specks).          |
| Stroke width  | Output stroke width, or **auto** (estimated from line weight).      |
| Stroke color  | Output stroke color.                                                |

## API

`POST /api/convert` (multipart form): field `file` plus the options above.
Returns JSON: `{ svg, width, height, path_count, stroke_width, stats }`.

## Project layout

```
app/
  main.py            FastAPI app + routes
  tracing/
    pipeline.py      orchestrates the full trace
    skeleton.py      skeleton → polylines (graph walk)
    bezier.py        RDP simplify + Catmull-Rom → Bézier
    svg.py           SVG document assembly
  static/            browser UI (index.html, app.js, style.css)
tests/               engine unit tests
samples/             demo input + output
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Best results

Designed for **clean line art**: solid dark lines on a light background (inked
drawings, logos, the kind of greeting-card illustration this was built for).
Photos and heavily shaded images are out of scope for now.
