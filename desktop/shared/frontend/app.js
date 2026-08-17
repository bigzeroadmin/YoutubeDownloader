const API = "/api";

let allFormats = [];
let currentTab = "video";

// Queue: [{taskId, formatLabel, filesize, status, progress, error, retries, pollTimer}]
const taskQueue = [];

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

/* ── Resolve ── */

async function handleResolve() {
  const url = $("#urlInput").value.trim();
  if (!url) return;

  const btn = $("#resolveBtn");
  const err = $("#errorMsg");
  hide(err);
  hide($("#videoInfo"));
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
  switchTab("video");
  show($("#videoInfo"));
}

/* ── Tabs & Format List ── */

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
      const inQueue = taskQueue.some(
        (t) => t.formatId === f.format_id && t.status !== "failed",
      );
      return `<div class="format-item" data-id="${f.format_id}">
                <span class="fmt-label">${label}</span>
                <span class="fmt-detail">${detail}</span>
                <button class="fmt-dl-btn"
                        onclick="startDownload('${f.format_id}')"
                        ${inQueue ? "disabled" : ""}>
                  ${inQueue ? "已添加" : "下载"}
                </button>
              </div>`;
    })
    .join("");
}

/* ── Download & Queue ── */

async function startDownload(formatId) {
  const url = $("#urlInput").value.trim();
  if (!url) return;

  const fmt = allFormats.find((f) => f.format_id === formatId);
  if (!fmt) return;

  const isAudio = currentTab === "audio";
  const label =
    currentTab === "video"
      ? `${fmt.resolution || "?"} · ${fmt.ext}`
      : `${fmt.ext} · ${fmt.abr ? fmt.abr + " kbps" : fmt.note || ""}`;

  // Add placeholder to queue immediately
  const entry = {
    taskId: null,
    formatId: formatId,
    formatLabel: label,
    filesize: fmt.filesize,
    status: "pending",
    progress: 0,
    error: null,
    retries: 0,
    pollTimer: null,
  };
  taskQueue.unshift(entry);
  renderFormats();
  renderQueue();

  try {
    const res = await fetch(`${API}/download`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url,
        format_id: formatId,
        audio_only: isAudio,
        convert_mp3: isAudio,
        has_audio: Boolean(fmt.acodec && fmt.acodec !== "none"),
        expected_filesize: fmt.filesize || null,
      }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    entry.taskId = data.task_id;
    pollTask(entry);
  } catch (e) {
    entry.status = "failed";
    entry.error = e.message;
    renderQueue();
    renderFormats();
  }
}

function pollTask(entry) {
  if (entry.pollTimer) clearInterval(entry.pollTimer);

  entry.pollTimer = setInterval(async () => {
    if (!entry.taskId) return;
    try {
      const res = await fetch(`${API}/tasks/${entry.taskId}`);
      if (!res.ok) return;
      const task = await res.json();

      entry.status = task.status;
      entry.progress = task.progress;
      entry.error = task.error;
      entry.retries = task.retries || 0;
      entry.cookieRetries = task.cookie_retries || 0;
      entry.taskFilesize = task.filesize;
      renderQueue();

      if (task.status === "success" || task.status === "failed") {
        clearInterval(entry.pollTimer);
        entry.pollTimer = null;
        renderFormats();
      }
    } catch {
      /* network hiccup, keep polling */
    }
  }, 1500);
}

/* ── Queue Rendering ── */

const STATUS_LABELS = {
  pending: "等待中",
  running: "下载中",
  success: "完成",
  failed: "失败",
  waiting_cookies: "等待Cookie刷新...",
};

function statusColor(status, retries) {
  if (status === "success") return "var(--success)";
  if (status === "failed") return "var(--error)";
  if (status === "waiting_cookies") return "var(--warning, #f59e0b)";
  if (retries > 0) return "var(--warning, #f59e0b)";
  return "var(--accent)";
}

function renderQueue() {
  const section = $("#queueSection");
  const list = $("#queueList");

  if (taskQueue.length === 0) {
    hide(section);
    return;
  }
  show(section);

  list.innerHTML = taskQueue
    .map((t, i) => {
      let label = STATUS_LABELS[t.status] || t.status;
      if (t.retries > 0 && t.status === "pending") label = `重试中 (${t.retries})`;
      else if (t.retries > 0 && t.status === "running") label = `下载中 (重试 ${t.retries})`;

      const pct = Math.round(t.progress);
      const color = statusColor(t.status, t.retries);
      const sizeStr = formatBytes(t.filesize);

      let extra = "";
      if (t.status === "failed" && t.error) {
        extra += `<p class="error">${escapeHtml(t.error)}</p>`;
      }
      if (t.status === "success" && t.taskId) {
        const dlSize = t.taskFilesize ? ` (${formatBytes(t.taskFilesize)})` : "";
        extra += `<a class="queue-dl-link" href="${API}/files/${t.taskId}">下载文件${dlSize}</a>`;
      }

      return `<div class="queue-item" data-idx="${i}">
        <div class="queue-item-header">
          <span class="queue-item-title">${escapeHtml(t.formatLabel)} · ${sizeStr}</span>
          <div class="queue-item-right">
            <span class="badge" style="background:${color};color:#fff">${label}</span>
            <span style="font-size:0.78rem;color:var(--text-muted)">${pct}%</span>
          </div>
        </div>
        <div class="queue-progress-bar">
          <div class="queue-progress-fill" style="width:${t.progress}%;background:${color}"></div>
        </div>
        ${extra}
      </div>`;
    })
    .join("");
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

/* ── Reset ── */

function handleReset() {
  const hasActive = taskQueue.some((t) =>
    ["pending", "running", "waiting_cookies"].includes(t.status),
  );
  if (
    hasActive &&
    !confirm("仍有下载任务在进行中，重置只会清空界面显示（后台任务不受影响）。确定重置吗？")
  ) {
    return;
  }

  taskQueue.forEach((t) => {
    if (t.pollTimer) clearInterval(t.pollTimer);
  });
  taskQueue.length = 0;
  allFormats = [];
  currentTab = "video";

  $("#urlInput").value = "";
  hide($("#errorMsg"));
  hide($("#videoInfo"));
  renderQueue(); // empties and hides the queue section
  document
    .querySelectorAll(".tab")
    .forEach((t) => t.classList.toggle("active", t.dataset.tab === "video"));

  const btn = $("#resolveBtn");
  btn.disabled = false;
  btn.textContent = "解析";
  $("#urlInput").focus();
}

/* ── Help Modal ── */

function openHelp() {
  show($("#helpOverlay"));
  document.body.style.overflow = "hidden";
}

function closeHelp() {
  hide($("#helpOverlay"));
  document.body.style.overflow = "";
}

function closeHelpOutside(e) {
  if (e.target === $("#helpOverlay")) closeHelp();
}

document.addEventListener("keydown", function (e) {
  if (e.key === "Escape" && !$("#helpOverlay").classList.contains("hidden")) {
    closeHelp();
  }
});
