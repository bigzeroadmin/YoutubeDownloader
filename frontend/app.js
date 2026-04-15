const API = "/api";

let allFormats = [];
let currentTab = "video";
let selectedFormatId = null;
let pollTimer = null;

function $(sel) {
  return document.querySelector(sel);
}

function show(el) {
  el.classList.remove("hidden");
}
function hide(el) {
  el.classList.add("hidden");
}

function formatBytes(bytes) {
  if (!bytes) return "—";
  const mb = bytes / 1048576;
  return mb >= 1024
    ? (mb / 1024).toFixed(1) + " GB"
    : mb.toFixed(1) + " MB";
}

function formatDuration(sec) {
  if (!sec) return "";
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

async function handleResolve() {
  const url = $("#urlInput").value.trim();
  if (!url) return;

  const btn = $("#resolveBtn");
  const err = $("#errorMsg");
  hide(err);
  hide($("#videoInfo"));
  hide($("#taskSection"));
  btn.disabled = true;
  btn.textContent = "解析中...";

  try {
    const res = await fetch(`${API}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    renderVideoInfo(data);
  } catch (e) {
    err.textContent = e.message;
    show(err);
  } finally {
    btn.disabled = false;
    btn.textContent = "解析";
  }
}

function renderVideoInfo(data) {
  $("#videoTitle").textContent = data.title;
  $("#thumbnail").src = data.thumbnail || "";
  $("#videoDuration").textContent = formatDuration(data.duration);

  allFormats = data.formats || [];
  selectedFormatId = null;
  switchTab("video");
  show($("#videoInfo"));
}

function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.tab === tab);
  });
  renderFormats();
}

function isVideoFormat(f) {
  return f.vcodec && f.vcodec !== "none";
}

function isAudioFormat(f) {
  return (
    (!f.vcodec || f.vcodec === "none") && f.acodec && f.acodec !== "none"
  );
}

function renderFormats() {
  const list = $("#formatList");
  const filtered =
    currentTab === "video"
      ? allFormats.filter(isVideoFormat)
      : allFormats.filter(isAudioFormat);

  if (filtered.length === 0) {
    list.innerHTML =
      '<div class="fmt-detail" style="padding:0.6rem;text-align:center">无可用格式</div>';
    return;
  }

  list.innerHTML = filtered
    .map((f) => {
      const label =
        currentTab === "video"
          ? `${f.resolution || "?"} · ${f.ext}`
          : `${f.ext} · ${f.abr ? f.abr + " kbps" : f.note || ""}`;
      const detail = formatBytes(f.filesize);
      return `<div class="format-item${f.format_id === selectedFormatId ? " selected" : ""}"
                   data-id="${f.format_id}"
                   onclick="selectFormat('${f.format_id}')">
                <span class="fmt-label">${label}</span>
                <span class="fmt-detail">${detail}</span>
              </div>`;
    })
    .join("");
}

function selectFormat(fmtId) {
  selectedFormatId = fmtId;
  renderFormats();
  startDownload();
}

async function startDownload() {
  if (!selectedFormatId) return;

  const url = $("#urlInput").value.trim();
  const isAudio = currentTab === "audio";

  hide($("#taskError"));
  hide($("#downloadLink"));
  show($("#taskSection"));
  updateTaskUI("pending", 0);

  try {
    const res = await fetch(`${API}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        format_id: selectedFormatId,
        audio_only: isAudio,
        convert_mp3: isAudio,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    pollTask(data.task_id);
  } catch (e) {
    updateTaskUI("failed", 0, e.message);
  }
}

function pollTask(taskId) {
  if (pollTimer) clearInterval(pollTimer);

  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API}/tasks/${taskId}`);
      if (!res.ok) return;
      const task = await res.json();

      updateTaskUI(task.status, task.progress, task.error, task.retries || 0);

      if (task.status === "success") {
        clearInterval(pollTimer);
        const link = $("#downloadLink");
        link.href = `${API}/files/${taskId}`;
        link.textContent = `下载文件${task.filesize ? " (" + formatBytes(task.filesize) + ")" : ""}`;
        show(link);
      } else if (task.status === "failed") {
        clearInterval(pollTimer);
      }
    } catch {
      /* network hiccup, keep polling */
    }
  }, 1500);
}

const STATUS_LABELS = {
  pending: "等待中",
  running: "下载中",
  success: "完成",
  failed: "失败",
};

function updateTaskUI(status, progress, error, retries) {
  const badge = $("#taskStatusBadge");
  let label = STATUS_LABELS[status] || status;
  if (retries > 0 && status === "pending") {
    label = `重试中 (${retries})`;
  } else if (retries > 0 && status === "running") {
    label = `下载中 (重试 ${retries})`;
  }
  badge.textContent = label;
  badge.style.background =
    status === "success"
      ? "var(--success)"
      : status === "failed"
        ? "var(--error)"
        : retries > 0
          ? "var(--warning, #f59e0b)"
          : "var(--accent)";
  badge.style.color = "#fff";

  $("#taskProgress").textContent = `${Math.round(progress)}%`;
  $("#progressFill").style.width = `${progress}%`;

  const errEl = $("#taskError");
  if (error && status === "failed") {
    errEl.textContent = error;
    show(errEl);
  } else {
    hide(errEl);
  }
}
