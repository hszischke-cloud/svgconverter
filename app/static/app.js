"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  file: null,
  svg: null,
};

const dropzone = $("dropzone");
const fileInput = $("fileInput");
const convertBtn = $("convertBtn");
const downloadBtn = $("downloadBtn");
const statusEl = $("status");

// --- Slider value labels -------------------------------------------------
const sliders = [
  ["mergeAngle", "mergeAngleVal", (v) => `${v}°`],
  ["spurLength", "spurLengthVal", (v) => v],
  ["smoothing", "smoothingVal", (v) => Number(v).toFixed(2)],
  ["simplify", "simplifyVal", (v) => Number(v).toFixed(2)],
  ["minObjectSize", "minObjectSizeVal", (v) => v],
];
for (const [id, outId, fmt] of sliders) {
  const el = $(id);
  el.addEventListener("input", () => ($(outId).textContent = fmt(el.value)));
}

// "auto" checkboxes enable/disable their paired slider.
$("autoThreshold").addEventListener("change", (e) => {
  $("threshold").disabled = e.target.checked;
});
$("autoStroke").addEventListener("change", (e) => {
  $("strokeWidth").disabled = e.target.checked;
});

// --- File selection ------------------------------------------------------
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) loadFile(fileInput.files[0]);
});

["dragover", "dragenter"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) loadFile(f);
});

function loadFile(file) {
  if (!file.type.startsWith("image/")) {
    setStatus("Please choose an image file.", true);
    return;
  }
  state.file = file;
  state.svg = null;
  downloadBtn.disabled = true;
  convertBtn.disabled = false;

  const reader = new FileReader();
  reader.onload = (e) => {
    $("originalView").innerHTML = `<img src="${e.target.result}" alt="original" />`;
  };
  reader.readAsDataURL(file);
  $("svgView").innerHTML = "";
  setStatus(`Loaded ${file.name}. Click Convert.`);
}

// --- Convert -------------------------------------------------------------
convertBtn.addEventListener("click", convert);

async function convert() {
  if (!state.file) return;
  setStatus("Tracing centerlines…");
  convertBtn.disabled = true;

  const fd = new FormData();
  fd.append("file", state.file);
  fd.append(
    "threshold",
    $("autoThreshold").checked ? "auto" : $("threshold").value
  );
  fd.append("invert", $("invert").checked);
  fd.append("min_object_size", $("minObjectSize").value);
  fd.append("merge_angle", $("mergeAngle").value);
  fd.append("spur_length", $("spurLength").value);
  fd.append("simplify", $("simplify").value);
  fd.append("smoothing", $("smoothing").value);
  fd.append(
    "stroke_width",
    $("autoStroke").checked ? "auto" : $("strokeWidth").value
  );
  fd.append("stroke_color", $("strokeColor").value);

  try {
    const res = await fetch("/api/convert", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    const data = await res.json();
    state.svg = data.svg;
    $("svgView").innerHTML = data.svg;
    downloadBtn.disabled = false;
    setStatus(
      `Done: ${data.path_count} paths, stroke width ${data.stroke_width}px.`
    );
  } catch (err) {
    setStatus(`Error: ${err.message}`, true);
  } finally {
    convertBtn.disabled = false;
  }
}

// --- Download ------------------------------------------------------------
downloadBtn.addEventListener("click", () => {
  if (!state.svg) return;
  const blob = new Blob([state.svg], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const base = (state.file?.name || "image").replace(/\.[^.]+$/, "");
  a.href = url;
  a.download = `${base}-centerline.svg`;
  a.click();
  URL.revokeObjectURL(url);
});

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.style.color = isError ? "#b3261e" : "";
}
