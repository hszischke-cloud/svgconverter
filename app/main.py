"""FastAPI web app: upload line art, get a centerline SVG back."""

from __future__ import annotations

import io
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

from .tracing import TraceParams, trace

app = FastAPI(title="Centerline SVG Converter")

STATIC_DIR = Path(__file__).parent / "static"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


def _parse_optional_int(value: str | None):
    if value is None or value == "" or value.lower() == "auto":
        return None
    return int(value)


def _parse_optional_float(value: str | None):
    if value is None or value == "" or value.lower() == "auto":
        return None
    return float(value)


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    threshold: str | None = Form(None),
    invert: bool = Form(False),
    min_object_size: int = Form(12),
    simplify: float = Form(1.5),
    smoothing: float = Form(1.0),
    min_path_length: int = Form(5),
    stroke_width: str | None = Form(None),
    stroke_color: str = Form("#1f3d1f"),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 25 MB).")

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image.")

    params = TraceParams(
        threshold=_parse_optional_int(threshold),
        invert=invert,
        min_object_size=max(0, min_object_size),
        simplify=max(0.0, simplify),
        smoothing=min(max(smoothing, 0.0), 1.0),
        min_path_length=max(0, min_path_length),
        stroke_width=_parse_optional_float(stroke_width),
        stroke_color=stroke_color,
    )

    try:
        result = trace(image, params)
    except Exception as exc:  # pragma: no cover - surface engine errors cleanly
        raise HTTPException(status_code=500, detail=f"Tracing failed: {exc}")

    return JSONResponse(
        {
            "svg": result.svg,
            "width": result.width,
            "height": result.height,
            "path_count": result.path_count,
            "stroke_width": result.stroke_width,
            "stats": result.stats,
        }
    )


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# Static assets (app.js, style.css). Mounted last so it doesn't shadow routes.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
