// ── Tab switching ─────────────────────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.tab}`).classList.add("active");
  });
});

// ── Radio pill styling helper ────────────────────────────────────────────
function wireRadioGroup(name) {
  document.querySelectorAll(`input[name="${name}"]`).forEach(input => {
    input.addEventListener("change", () => {
      document.querySelectorAll(`input[name="${name}"]`).forEach(i => {
        i.closest(".radio-opt").classList.toggle("checked", i.checked);
      });
    });
  });
}
["axis", "liveSrcType", "liveAxis", "speed", "liveSpeed"].forEach(wireRadioGroup);

const themeSwitcher = document.getElementById("themeSwitcher");
const THEMES = [
  { id: "midnight", label: "Midnight", color: "#2dd4bf" },
  { id: "studio", label: "Studio", color: "#4f46e5" },
  { id: "terracotta", label: "Terracotta", color: "#c1552c" },
  { id: "amber", label: "Amber", color: "#f5b31c" },
  { id: "pastel", label: "Pastel", color: "#8b5cf6" },
];

function setTheme(themeId) {
  document.documentElement.dataset.theme = themeId;
  localStorage.setItem("carCounterTheme", themeId);
  themeSwitcher.querySelectorAll(".theme-chip").forEach(chip => {
    chip.classList.toggle("active", chip.dataset.theme === themeId);
  });
}

function buildThemeSwitcher() {
  if (!themeSwitcher) return;
  themeSwitcher.innerHTML = THEMES.map(theme => `
    <button type="button" class="theme-chip" data-theme="${theme.id}">
      <span class="theme-chip-dot" style="background:${theme.color}"></span>
      ${theme.label}
    </button>
  `).join("");
  themeSwitcher.querySelectorAll(".theme-chip").forEach(chip => {
    chip.addEventListener("click", () => setTheme(chip.dataset.theme));
  });
  const stored = localStorage.getItem("carCounterTheme") || "midnight";
  setTheme(THEMES.some(t => t.id === stored) ? stored : "midnight");
}

buildThemeSwitcher();

// ── Upload tab ────────────────────────────────────────────────────────────
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileChip = document.getElementById("fileChip");
const fileChipName = document.getElementById("fileChipName");
const fileChipClear = document.getElementById("fileChipClear");
const submitBtn = document.getElementById("submitBtn");
const confRange = document.getElementById("confRange");
const confVal = document.getElementById("confVal");
const durationRange = document.getElementById("durationRange");
const durationVal = document.getElementById("durationVal");
const durationHint = document.getElementById("durationHint");
const lineLengthRange = document.getElementById("lineLengthRange");
const lineLengthVal = document.getElementById("lineLengthVal");

let selectedFile = null;
let videoTotalSeconds = null;

confRange.addEventListener("input", () => confVal.textContent = parseFloat(confRange.value).toFixed(2));
lineLengthRange.addEventListener("input", () => {
  lineLengthVal.textContent = `${Math.round(parseFloat(lineLengthRange.value) * 100)}%`;
});

function formatSeconds(s) {
  s = Math.round(s);
  const m = Math.floor(s / 60), sec = s % 60;
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
}

durationRange.addEventListener("input", () => {
  const v = parseInt(durationRange.value, 10);
  const full = videoTotalSeconds ? Math.ceil(videoTotalSeconds) : v;
  durationVal.textContent = v >= full ? "Full" : formatSeconds(v);
});

function probeVideoDuration(file) {
  const url = URL.createObjectURL(file);
  const probe = document.createElement("video");
  probe.preload = "metadata";
  probe.onloadedmetadata = () => {
    const dur = probe.duration;
    URL.revokeObjectURL(url);
    if (isFinite(dur) && dur > 0) {
      videoTotalSeconds = dur;
      const maxSec = Math.max(1, Math.ceil(dur));
      durationRange.min = 1;
      durationRange.max = maxSec;
      durationRange.value = maxSec;
      durationRange.disabled = false;
      durationVal.textContent = "Full";
      durationHint.textContent = `Video is ${formatSeconds(dur)} long. Drag left to process only the first N seconds.`;
    } else {
      videoTotalSeconds = null;
      durationRange.disabled = true;
      durationVal.textContent = "—";
      durationHint.textContent = "Couldn't read video length — full video will be processed.";
    }
  };
  probe.onerror = () => {
    URL.revokeObjectURL(url);
    videoTotalSeconds = null;
    durationRange.disabled = true;
    durationVal.textContent = "—";
    durationHint.textContent = "Couldn't read video length — full video will be processed.";
  };
  probe.src = url;
}

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", e => { e.preventDefault(); dropzone.classList.add("drag"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag"));
dropzone.addEventListener("drop", e => {
  e.preventDefault();
  dropzone.classList.remove("drag");
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => { if (fileInput.files.length) setFile(fileInput.files[0]); });

fileChipClear.addEventListener("click", e => {
  e.stopPropagation();
  selectedFile = null;
  fileInput.value = "";
  fileChip.classList.remove("show");
  submitBtn.disabled = true;
  videoTotalSeconds = null;
  durationRange.disabled = true;
  durationRange.value = 1;
  durationVal.textContent = "—";
  durationHint.textContent = "Select a video to set this.";
});

function setFile(file) {
  selectedFile = file;
  fileChipName.textContent = `${file.name}  ·  ${(file.size / (1024 * 1024)).toFixed(1)} MB`;
  fileChip.classList.add("show");
  submitBtn.disabled = false;
  probeVideoDuration(file);
}

const uploadForm = document.getElementById("uploadForm");
const jobStatusLine = document.getElementById("jobStatusLine");
const jobStatusDot = document.getElementById("jobStatusDot");
const jobStatusText = document.getElementById("jobStatusText");
const progressWrap = document.getElementById("progressWrap");
const progressFill = document.getElementById("progressFill");
const progressPct = document.getElementById("progressPct");
const progressFrames = document.getElementById("progressFrames");
const jobStopBtn = document.getElementById("jobStopBtn");
const resultEmpty = document.getElementById("resultEmpty");
const resultPreview = document.getElementById("resultPreview");
const previewImg = document.getElementById("previewImg");
const resultBody = document.getElementById("resultBody");
let previewJobId = null;
const resultVideo = document.getElementById("resultVideo");
const resultNote = document.getElementById("resultNote");
const resultIn = document.getElementById("resultIn");
const resultOut = document.getElementById("resultOut");
const downloadVideo = document.getElementById("downloadVideo");
const downloadCsv = document.getElementById("downloadCsv");
const heroIn = document.getElementById("heroIn");
const heroOut = document.getElementById("heroOut");
const jobHistory = document.getElementById("jobHistory");

let pollTimer = null;
let currentJobId = null;

jobStopBtn.addEventListener("click", async () => {
  if (!currentJobId) return;
  jobStopBtn.disabled = true;
  jobStopBtn.textContent = "Stopping…";
  try {
    await fetch(`/api/jobs/${currentJobId}/stop`, { method: "POST" });
  } catch (err) {
    // next poll will reflect actual state either way
  }
});

uploadForm.addEventListener("submit", async e => {
  e.preventDefault();
  if (!selectedFile) return;

  submitBtn.disabled = true;
  submitBtn.textContent = "Uploading…";
  resultBody.style.display = "none";
  resultPreview.style.display = "none";
  previewJobId = null;
  resultEmpty.style.display = "block";
  resultEmpty.textContent = "Uploading video…";
  jobStopBtn.style.display = "none";
  jobStopBtn.disabled = false;
  jobStopBtn.textContent = "■ Stop processing";

  const axis = document.querySelector('input[name="axis"]:checked').value;
  const fd = new FormData();
  fd.append("file", selectedFile);
  fd.append("conf", confRange.value);
  fd.append("line_axis", axis);
  fd.append("line_length", lineLengthRange.value);
  fd.append("imgsz", document.querySelector('input[name="speed"]:checked').value);

  const requestedSec = parseInt(durationRange.value, 10);
  const isFullLength = !videoTotalSeconds || requestedSec >= Math.ceil(videoTotalSeconds);
  if (!isFullLength) fd.append("max_duration", requestedSec);

  try {
    const res = await fetch("/api/jobs", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "Upload failed");
    const job = await res.json();
    currentJobId = job.id;
    jobStatusLine.style.display = "flex";
    progressWrap.style.display = "block";
    resultEmpty.textContent = "Processing…";
    pollJob(job.id);
    loadJobHistory();
  } catch (err) {
    resultEmpty.textContent = `Upload failed: ${err.message}`;
    submitBtn.disabled = false;
    submitBtn.textContent = "Process video";
  }
});

function pollJob(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    const res = await fetch(`/api/jobs/${jobId}`);
    if (!res.ok) return;
    const job = await res.json();
    updateJobUI(job);
    if (job.status === "complete" || job.status === "failed" || job.status === "cancelled") {
      clearInterval(pollTimer);
      submitBtn.disabled = !selectedFile;
      submitBtn.textContent = "Process video";
      jobStopBtn.style.display = "none";
      loadJobHistory();
    }
  }, 900);
}

function updateJobUI(job) {
  jobStatusDot.className = `status-dot ${job.status}`;
  const pct = Math.round(job.progress * 100);
  progressFill.style.width = `${pct}%`;
  progressPct.textContent = `${pct}%`;
  progressFrames.textContent = `${job.processed_frames} / ${job.total_frames || "?"} frames`;
  heroIn.textContent = job.in_count;
  heroOut.textContent = job.out_count;

  if (job.status === "queued") jobStatusText.textContent = "Queued…";
  else if (job.status === "processing") jobStatusText.textContent = "Processing frames…";
  else if (job.status === "complete") jobStatusText.textContent = "Complete";
  else if (job.status === "cancelled") jobStatusText.textContent = "Stopped";
  else if (job.status === "failed") jobStatusText.textContent = `Failed — ${job.error || "unknown error"}`;

  jobStopBtn.style.display = (job.status === "queued" || job.status === "processing") ? "block" : "none";

  if (job.status === "queued" || job.status === "processing") {
    resultEmpty.style.display = "none";
    resultBody.style.display = "none";
    resultPreview.style.display = "block";
    if (previewJobId !== job.id) {
      // only (re)point the <img> at a new stream once per job, so we don't
      // keep reconnecting the MJPEG stream on every status poll
      previewImg.src = `/api/jobs/${job.id}/preview`;
      previewJobId = job.id;
    }
  } else if ((job.status === "complete" || job.status === "cancelled") && job.has_video) {
    resultPreview.style.display = "none";
    resultEmpty.style.display = "none";
    resultBody.style.display = "block";
    resultVideo.src = `/api/jobs/${job.id}/video`;
    resultIn.textContent = job.in_count;
    resultOut.textContent = job.out_count;
    downloadVideo.href = `/api/jobs/${job.id}/video`;
    downloadCsv.href = job.has_csv ? `/api/jobs/${job.id}/csv` : "#";
    downloadCsv.style.opacity = job.has_csv ? 1 : 0.4;
    resultNote.style.display = job.status === "cancelled" ? "block" : "none";
    resultNote.textContent = `Stopped early — this is a partial result covering ${job.processed_frames} of ${job.total_frames || "?"} frames.`;
  } else if (job.status === "cancelled") {
    resultPreview.style.display = "none";
    resultBody.style.display = "none";
    resultEmpty.style.display = "block";
    resultEmpty.textContent = "Stopped before any frames were saved.";
  } else if (job.status === "failed") {
    resultPreview.style.display = "none";
    resultEmpty.style.display = "block";
    resultBody.style.display = "none";
    resultEmpty.textContent = `Processing failed: ${job.error || "unknown error"}`;
  }
}

async function loadJobHistory() {
  const res = await fetch("/api/jobs");
  if (!res.ok) return;
  const jobs = await res.json();
  if (!jobs.length) {
    jobHistory.innerHTML = `<div class="empty-note">Processed videos will appear here.</div>`;
    return;
  }
  jobHistory.innerHTML = jobs.slice(0, 8).map(j => `
    <div class="job-item" data-id="${j.id}">
      <div class="job-item-main">
        <span class="jn">${j.filename || j.id}</span>
        <span class="js ${j.status}">${j.status.toUpperCase()} · IN ${j.in_count} / OUT ${j.out_count}</span>
      </div>
      <button class="job-delete" type="button" data-id="${j.id}" title="Delete this record">✕</button>
    </div>
  `).join("");
  jobHistory.querySelectorAll(".job-item").forEach(el => {
    el.addEventListener("click", async event => {
      if (event.target.closest(".job-delete")) return;
      const res = await fetch(`/api/jobs/${el.dataset.id}`);
      if (!res.ok) return;
      const job = await res.json();
      document.querySelector('.tab-btn[data-tab="upload"]').click();
      currentJobId = job.id;
      jobStatusLine.style.display = "flex";
      progressWrap.style.display = "block";
      jobStopBtn.disabled = false;
      jobStopBtn.textContent = "■ Stop processing";
      updateJobUI(job);
      if (job.status === "processing" || job.status === "queued") pollJob(job.id);
    });
    const delBtn = el.querySelector(".job-delete");
    delBtn.addEventListener("click", async event => {
      event.stopPropagation();
      const jobId = delBtn.dataset.id;
      if (!confirm("Delete this job record and its files?")) return;
      const res = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
      if (!res.ok) return;
      if (currentJobId === jobId) {
        currentJobId = null;
        jobStatusLine.style.display = "none";
        progressWrap.style.display = "none";
        resultPreview.style.display = "none";
        resultBody.style.display = "none";
        resultEmpty.style.display = "block";
        resultEmpty.textContent = "Selected job was deleted.";
      }
      loadJobHistory();
      loadArchive();
    });
  });
}
loadJobHistory();

// ── Live tab ──────────────────────────────────────────────────────────────
const webcamField = document.getElementById("webcamField");
const rtspField = document.getElementById("rtspField");
document.querySelectorAll('input[name="liveSrcType"]').forEach(r => {
  r.addEventListener("change", () => {
    const isWebcam = document.querySelector('input[name="liveSrcType"]:checked').value === "webcam";
    webcamField.style.display = isWebcam ? "block" : "none";
    rtspField.style.display = isWebcam ? "none" : "block";
  });
});

const liveConfRange = document.getElementById("liveConfRange");
const liveConfVal = document.getElementById("liveConfVal");
liveConfRange.addEventListener("input", () => liveConfVal.textContent = parseFloat(liveConfRange.value).toFixed(2));

const liveLineLengthRange = document.getElementById("liveLineLengthRange");
const liveLineLengthVal = document.getElementById("liveLineLengthVal");
liveLineLengthRange.addEventListener("input", () => {
  liveLineLengthVal.textContent = `${Math.round(parseFloat(liveLineLengthRange.value) * 100)}%`;
});

const liveStartBtn = document.getElementById("liveStartBtn");
const liveStopBtn = document.getElementById("liveStopBtn");
const liveRecBtn = document.getElementById("liveRecBtn");
const liveStage = document.getElementById("liveStage");
const liveStatusLine = document.getElementById("liveStatusLine");
const liveStatusDot = document.getElementById("liveStatusDot");
const liveStatusText = document.getElementById("liveStatusText");
const liveHeroIn = document.getElementById("liveHeroIn");
const liveHeroOut = document.getElementById("liveHeroOut");
const liveCaptionLeft = document.getElementById("liveCaptionLeft");

let liveSessionId = null;
let livePollTimer = null;

liveStartBtn.addEventListener("click", async () => {
  const srcType = document.querySelector('input[name="liveSrcType"]:checked').value;
  const axis = document.querySelector('input[name="liveAxis"]:checked').value;
  const sourceValue = srcType === "webcam"
    ? document.getElementById("webcamIndex").value.trim()
    : document.getElementById("rtspUrl").value.trim();

  if (srcType === "rtsp" && !sourceValue) {
    alert("Enter an RTSP stream URL first.");
    return;
  }

  liveStartBtn.disabled = true;
  liveStartBtn.textContent = "Connecting…";
  liveStatusLine.style.display = "flex";
  liveStatusDot.className = "status-dot processing";
  liveStatusText.textContent = "Connecting to source…";

  try {
    const res = await fetch("/api/live/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_type: srcType, source_value: sourceValue,
        conf: parseFloat(liveConfRange.value), line_axis: axis,
        line_length: parseFloat(liveLineLengthRange.value),
        imgsz: parseInt(document.querySelector('input[name="liveSpeed"]:checked').value, 10),
      }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Could not start source");
    const data = await res.json();
    liveSessionId = data.session_id;

    liveStage.innerHTML = `<img src="/api/live/${liveSessionId}/feed" alt="Live annotated feed">
      <div class="live-badge running" id="liveBadge"><span class="dot"></span>LIVE</div>`;
    liveCaptionLeft.textContent = srcType === "webcam" ? `WEBCAM ${sourceValue}` : "RTSP SOURCE";
    liveStopBtn.disabled = false;
    liveRecBtn.disabled = false;
    liveStartBtn.textContent = "Restart stream";
    pollLiveStatus();
  } catch (err) {
    liveStatusDot.className = "status-dot failed";
    liveStatusText.textContent = err.message;
    liveStartBtn.disabled = false;
    liveStartBtn.textContent = "Start stream";
  }
});

function pollLiveStatus() {
  clearInterval(livePollTimer);
  livePollTimer = setInterval(async () => {
    if (!liveSessionId) return;
    const res = await fetch(`/api/live/${liveSessionId}/status`);
    if (!res.ok) return;
    const s = await res.json();
    liveHeroIn.textContent = s.in_count;
    liveHeroOut.textContent = s.out_count;
    liveRecBtn.classList.toggle("on", s.is_recording);
    liveRecBtn.textContent = s.is_recording ? "■ Stop recording" : "● Record";

    if (s.status === "running") {
      liveStatusDot.className = "status-dot processing";
      liveStatusText.textContent = `Live — ${s.n_dets} vehicle(s) in frame`;
    } else if (s.status === "stopped") {
      liveStatusDot.className = "status-dot";
      liveStatusText.textContent = "Stream stopped.";
      resetLiveButtons();
      clearInterval(livePollTimer);
    } else if (s.status === "error") {
      liveStatusDot.className = "status-dot failed";
      liveStatusText.textContent = s.error || "Stream error.";
      resetLiveButtons();
      clearInterval(livePollTimer);
    }
  }, 800);
}

function resetLiveButtons() {
  liveStartBtn.disabled = false;
  liveStartBtn.textContent = "Start stream";
  liveStopBtn.disabled = true;
  liveRecBtn.disabled = true;
  liveRecBtn.classList.remove("on");
  liveRecBtn.textContent = "● Record";
  const badge = document.getElementById("liveBadge");
  if (badge) badge.className = "live-badge error";
}

liveStopBtn.addEventListener("click", async () => {
  if (!liveSessionId) return;
  await fetch(`/api/live/${liveSessionId}/stop`, { method: "POST" });
  clearInterval(livePollTimer);
  resetLiveButtons();
  liveStage.innerHTML = `<div class="live-placeholder">Start a stream to see the annotated feed here.</div>`;
  liveCaptionLeft.textContent = "NO SOURCE CONNECTED";
});

liveRecBtn.addEventListener("click", async () => {
  if (!liveSessionId) return;
  const res = await fetch(`/api/live/${liveSessionId}/record`, { method: "POST" });
  if (!res.ok) return;
  const s = await res.json();
  liveRecBtn.classList.toggle("on", s.is_recording);
  liveRecBtn.textContent = s.is_recording ? "■ Stop recording" : "● Record";
});

// ── Archive tab ───────────────────────────────────────────────────────────
const archiveTableBody = document.getElementById("archiveTableBody");
const archiveEmpty = document.getElementById("archiveEmpty");
const archiveStatJobs = document.getElementById("archiveStatJobs");
const archiveStatVehicles = document.getElementById("archiveStatVehicles");
const filterDateFrom = document.getElementById("filterDateFrom");
const filterDateTo = document.getElementById("filterDateTo");
const filterStatus = document.getElementById("filterStatus");
const filterSource = document.getElementById("filterSource");
const filterReset = document.getElementById("filterReset");

const CLASS_ORDER = ["car", "truck", "bus", "motorcycle"];
const STATUS_LABELS = { complete: "Completed", partial: "Partial", cancelled: "Cancelled", failed: "Failed" };

let archiveJobs = [];
let archiveSort = { key: "created_at", dir: "desc" };

// Batch jobs only report a single terminal `status` (complete/cancelled/failed).
// The archive's "Partial" bucket is derived, not a real backend state: a
// cancelled job that still produced output is a partial result.
function archiveDisplayStatus(job) {
  if (job.status === "complete") return "complete";
  if (job.status === "cancelled") return job.has_video ? "partial" : "cancelled";
  if (job.status === "failed") return "failed";
  return null; // queued / processing jobs aren't finished yet — not shown here
}

function formatDuration(seconds) {
  if (seconds == null) return "—";
  seconds = Math.round(seconds);
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function formatArchiveDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function classBreakdownText(counts) {
  return CLASS_ORDER.map(c => `${c[0].toUpperCase()}${c.slice(1)} ${counts?.[c] ?? 0}`).join(" · ");
}

async function loadArchive() {
  const res = await fetch("/api/jobs");
  if (!res.ok) return;
  archiveJobs = await res.json();
  renderArchive();
}

function applyArchiveFilters(jobs) {
  const from = filterDateFrom.value ? new Date(filterDateFrom.value) : null;
  const to = filterDateTo.value ? new Date(filterDateTo.value) : null;
  const status = filterStatus.value;
  const source = filterSource.value.trim().toLowerCase();

  return jobs.filter(job => {
    const displayStatus = archiveDisplayStatus(job);
    if (!displayStatus) return false;
    if (status !== "all" && displayStatus !== status) return false;
    if (source && !(job.filename || "").toLowerCase().includes(source)) return false;
    if (from || to) {
      const created = job.created_at ? new Date(job.created_at) : null;
      if (!created) return false;
      if (from && created < from) return false;
      if (to) {
        const toEnd = new Date(to);
        toEnd.setHours(23, 59, 59, 999);
        if (created > toEnd) return false;
      }
    }
    return true;
  });
}

function sortArchiveJobs(jobs) {
  const { key, dir } = archiveSort;
  const mul = dir === "asc" ? 1 : -1;
  return [...jobs].sort((a, b) => {
    let av, bv;
    if (key === "total_count") {
      av = a.in_count + a.out_count; bv = b.in_count + b.out_count;
    } else if (key === "display_status") {
      av = archiveDisplayStatus(a); bv = archiveDisplayStatus(b);
    } else {
      av = a[key]; bv = b[key];
    }
    if (av == null) av = "";
    if (bv == null) bv = "";
    if (av < bv) return -1 * mul;
    if (av > bv) return 1 * mul;
    return 0;
  });
}

function renderArchive() {
  const filtered = applyArchiveFilters(archiveJobs);
  const sorted = sortArchiveJobs(filtered);

  archiveStatJobs.textContent = sorted.length;
  archiveStatVehicles.textContent = sorted.reduce((sum, j) => sum + j.in_count + j.out_count, 0);
  archiveEmpty.style.display = sorted.length ? "none" : "block";

  archiveTableBody.innerHTML = sorted.map(job => {
    const displayStatus = archiveDisplayStatus(job);
    const total = job.in_count + job.out_count;
    return `
      <tr class="archive-row" data-id="${job.id}">
        <td class="expand-cell"><span class="chevron">▸</span></td>
        <td class="jn">${job.filename || job.id}</td>
        <td class="mono">${formatArchiveDate(job.created_at)}</td>
        <td class="mono">${formatDuration(job.duration_seconds)}</td>
        <td class="mono">${total}</td>
        <td class="mini-breakdown">${classBreakdownText(job.class_counts)}</td>
        <td><span class="status-badge ${displayStatus}">${STATUS_LABELS[displayStatus]}</span></td>
      </tr>
      <tr class="archive-detail" data-detail-for="${job.id}" style="display:none;">
        <td colspan="7">
          <div class="detail-panel">
            <div class="detail-classes">
              ${CLASS_ORDER.map(c => `
                <div class="detail-class">
                  <span class="lbl">${c}</span>
                  <span class="val">${job.class_counts?.[c] ?? 0}</span>
                </div>
              `).join("")}
              <div class="detail-class">
                <span class="lbl">In / Out</span>
                <span class="val">${job.in_count} / ${job.out_count}</span>
              </div>
            </div>
            <div class="detail-actions">
              ${job.has_video ? `<a class="btn btn-ghost" href="/api/jobs/${job.id}/video" download>Download video</a>` : ""}
              ${job.has_csv ? `<a class="btn btn-ghost" href="/api/jobs/${job.id}/csv" download>Download CSV log</a>` : ""}
              <button class="btn btn-danger delete-job-btn" type="button" data-id="${job.id}">Delete record</button>
            </div>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  archiveTableBody.querySelectorAll(".archive-row").forEach(row => {
    row.addEventListener("click", () => {
      const detail = archiveTableBody.querySelector(`.archive-detail[data-detail-for="${row.dataset.id}"]`);
      const isOpen = row.classList.toggle("open");
      detail.style.display = isOpen ? "table-row" : "none";
    });
  });

  archiveTableBody.querySelectorAll(".delete-job-btn").forEach(btn => {
    btn.addEventListener("click", async event => {
      event.stopPropagation();
      const jobId = btn.dataset.id;
      if (!confirm("Delete this job record and its files?")) return;
      const res = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
      if (!res.ok) return;
      if (currentJobId === jobId) {
        currentJobId = null;
        jobStatusLine.style.display = "none";
        progressWrap.style.display = "none";
        resultPreview.style.display = "none";
        resultBody.style.display = "none";
        resultEmpty.style.display = "block";
        resultEmpty.textContent = "Selected job was deleted.";
      }
      loadJobHistory();
      loadArchive();
    });
  });
}

document.querySelectorAll(".archive-table thead th[data-sort]").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    archiveSort = { key, dir: archiveSort.key === key && archiveSort.dir === "asc" ? "desc" : "asc" };
    document.querySelectorAll(".archive-table thead .sort-arrow").forEach(a => a.className = "sort-arrow");
    th.querySelector(".sort-arrow").classList.add(archiveSort.dir);
    renderArchive();
  });
});

[filterDateFrom, filterDateTo, filterStatus].forEach(el => el.addEventListener("change", renderArchive));
filterSource.addEventListener("input", renderArchive);
filterReset.addEventListener("click", () => {
  filterDateFrom.value = "";
  filterDateTo.value = "";
  filterStatus.value = "all";
  filterSource.value = "";
  renderArchive();
});

document.querySelector('.tab-btn[data-tab="archive"]').addEventListener("click", loadArchive);
