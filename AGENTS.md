# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

YouTube 视频/音频下载桌面应用。基于 Electron + Python (FastAPI) + yt-dlp + ffmpeg，支持 macOS 和 Windows 双平台。

## Build & Run Commands

```bash
# macOS 开发模式
cd desktop
npm install
npm run macos

# macOS 构建
cd desktop/macos
npm install
npm run prebuild    # 下载 Python/ffmpeg/node 二进制
npm run build       # 构建 DMG

# Windows 开发模式
cd desktop
npm install
npm run windows

# Windows 构建
cd desktop/windows
npm install
npm run build
```

## Architecture

```
Electron App
├── main.js (Node.js) → 启动 Python 后端
├── BrowserWindow → 加载 http://127.0.0.1:{port}/
└── Python Backend (FastAPI + yt-dlp + ffmpeg)
```

### 请求流程

1. **启动**：Electron 主进程启动 Python 后端（uvicorn），等待健康检查通过
2. **解析**：前端 POST `/api/resolve` → `ytdlp_service.resolve_formats()` 提取视频格式列表（91porn 链接走 `porn91_service` 自研解析：yt-dlp 官方拒绝该站，需抓取页面解码 `strencode2` 混淆块，并多次采样选取最大镜像地址）
3. **下载**：前端 POST `/api/download` → 创建内存任务 → 后台线程执行 yt-dlp
4. **轮询**：前端每 1.5 秒 GET `/api/tasks/:id` 查询进度
5. **取件**：任务完成后 GET `/api/files/:id` 下载文件

### Key Design Decisions

- **桌面模式**：`DESKTOP_MODE=1` 时使用内存任务管理器，不依赖 Redis
- **yt-dlp 调用是同步阻塞的**：通过 `ThreadPoolExecutor` + `asyncio.run_in_executor` 包装
- **DASH 合并**：视频流和音频流分离时自动合并，需 ffmpeg
- **二进制打包**：Python/ffmpeg/node 作为 extraResources 打包进应用

## Directory Structure

```
desktop/
├── shared/                    # 公共代码
│   ├── backend/              # FastAPI 后端
│   │   ├── app/
│   │   │   ├── config.py     # 全局配置
│   │   │   ├── models.py     # Pydantic 模型
│   │   │   ├── main.py       # FastAPI 入口
│   │   │   ├── worker.py     # 下载执行（含 DASH 合并逻辑）
│   │   │   ├── routes/       # API 路由
│   │   │   └── services/     # yt-dlp 封装 + 91porn 自研解析（porn91_service.py）
│   │   └── requirements.txt
│   └── frontend/             # 前端 HTML/CSS/JS
├── macos/                     # macOS 版本
│   ├── src/main.js           # Electron 主进程
│   ├── scripts/              # 构建脚本
│   ├── resources/            # Python/ffmpeg/node 二进制
│   └── electron-builder.yml
└── windows/                   # Windows 版本
    ├── src/main.js           # Electron 主进程
    ├── scripts/              # 构建脚本（模板）
    └── electron-builder.yml
```

## Tech Stack Details

- Electron 33（桌面框架）
- Python 3.12 / FastAPI / Pydantic v2 / uvicorn
- yt-dlp（YouTube 解析与下载）+ ffmpeg（音视频合并转码）+ Node.js（YouTube n-parameter 签名）
- 前端：纯 HTML/CSS/JS 单页应用，无构建工具
- 所有配置通过环境变量驱动，定义在 `desktop/shared/backend/app/config.py`
