const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("child_process");
const net = require("net");
const path = require("path");
const fs = require("fs");
const http = require("http");
const os = require("os");

let mainWindow = null;
let pythonProcess = null;
let backendPort = null;

// ---------------------------------------------------------------------------
// Path resolution
// ---------------------------------------------------------------------------

function getResourcesDir() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  // Development: resources sit beside desktop/
  return path.join(__dirname, "..", "resources");
}

function getPythonBin() {
  const res = getResourcesDir();
  return path.join(res, "python", "bin", "python3.12");
}

function getBackendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "backend");
  }
  // Development: backend is in desktop/shared/backend
  return path.join(__dirname, "..", "..", "shared", "backend");
}

function getFrontendDir() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, "frontend");
  }
  // Development: frontend is in desktop/shared/frontend
  return path.join(__dirname, "..", "..", "shared", "frontend");
}

function getBundledBinDirs() {
  const res = getResourcesDir();
  return [
    path.join(res, "ffmpeg"),
    path.join(res, "node"),
  ].filter((p) => fs.existsSync(p));
}

// ---------------------------------------------------------------------------
// Free port discovery
// ---------------------------------------------------------------------------

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

// ---------------------------------------------------------------------------
// Backend health check
// ---------------------------------------------------------------------------

function waitForBackend(port, timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/auth/status`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          retry();
        }
      });
      req.on("error", retry);
      req.setTimeout(2000, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) {
        reject(new Error("Backend failed to start within timeout"));
        return;
      }
      setTimeout(check, 500);
    };
    check();
  });
}

// ---------------------------------------------------------------------------
// Log directory
// ---------------------------------------------------------------------------

function getLogDir() {
  const logDir = path.join(os.homedir(), "Library", "Logs", "YouTubeDownload");
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }
  return logDir;
}

// ---------------------------------------------------------------------------
// Start Python backend
// ---------------------------------------------------------------------------

async function startBackend() {
  backendPort = await findFreePort();
  const pythonBin = getPythonBin();
  const backendDir = getBackendDir();
  const frontendDir = getFrontendDir();
  const resourcesDir = getResourcesDir();

  // Build PATH with bundled binaries
  const extraPaths = getBundledBinDirs();
  const envPath = [...extraPaths, process.env.PATH || ""].join(path.delimiter);

  // DYLD_LIBRARY_PATH for ffmpeg's bundled dylibs
  const ffmpegLibDir = path.join(resourcesDir, "ffmpeg", "lib");
  const dyldPath = [ffmpegLibDir, process.env.DYLD_LIBRARY_PATH || ""]
    .filter(Boolean)
    .join(path.delimiter);

  const env = {
    ...process.env,
    DESKTOP_MODE: "1",
    ELECTRON_RESOURCES_PATH: resourcesDir,
    PYTHONPATH: backendDir,
    PATH: envPath,
    DYLD_LIBRARY_PATH: dyldPath,
    PYTHONDONTWRITEBYTECODE: "1",
  };

  const args = [
    "-m", "uvicorn",
    "app.main:app",
    "--host", "127.0.0.1",
    "--port", String(backendPort),
  ];

  console.log(`Starting backend: ${pythonBin} ${args.join(" ")}`);
  console.log(`Backend dir: ${backendDir}`);
  console.log(`Port: ${backendPort}`);

  pythonProcess = spawn(pythonBin, args, {
    cwd: backendDir,
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  // Log output
  const logDir = getLogDir();
  const logStream = fs.createWriteStream(path.join(logDir, "backend.log"), { flags: "a" });
  const timestamp = () => new Date().toISOString();

  pythonProcess.stdout.on("data", (data) => {
    const msg = data.toString();
    console.log(`[backend] ${msg}`);
    logStream.write(`${timestamp()} [stdout] ${msg}`);
  });
  pythonProcess.stderr.on("data", (data) => {
    const msg = data.toString();
    console.error(`[backend] ${msg}`);
    logStream.write(`${timestamp()} [stderr] ${msg}`);
  });
  pythonProcess.on("close", (code) => {
    console.log(`Backend exited with code ${code}`);
    logStream.write(`${timestamp()} [exit] code=${code}\n`);
    logStream.end();
    pythonProcess = null;
  });

  // Wait for backend to be ready
  await waitForBackend(backendPort);
  console.log("Backend is ready");
}

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 860,
    height: 720,
    minWidth: 500,
    minHeight: 500,
    backgroundColor: "#0f0f11",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  mainWindow.loadURL(`http://127.0.0.1:${backendPort}/`);

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  try {
    await startBackend();
    createWindow();
  } catch (err) {
    console.error("Failed to start:", err);
    dialog.showErrorBox(
      "Startup Error",
      `Failed to start the backend server.\n\n${err.message}\n\nCheck logs at ~/Library/Logs/YouTubeDownload/`
    );
    app.quit();
  }
});

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (mainWindow === null && backendPort) {
    createWindow();
  }
});

app.on("before-quit", () => {
  if (pythonProcess) {
    console.log("Sending SIGTERM to Python backend...");
    pythonProcess.kill("SIGTERM");

    // Force kill after 5 seconds
    const killTimer = setTimeout(() => {
      if (pythonProcess) {
        console.log("Force killing Python backend...");
        pythonProcess.kill("SIGKILL");
      }
    }, 5000);

    pythonProcess.on("close", () => {
      clearTimeout(killTimer);
    });
  }
});
