# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

私有部署的 YouTube 视频/音频下载工具。基于 yt-dlp + FastAPI + Redis + Nginx，通过 Docker Compose 一键部署四个服务（Redis / API / Worker / Nginx）。

## Build & Run Commands

```bash
# Docker 部署（生产）
docker compose up -d --build
docker compose down
docker compose logs api --tail 20

# 本地开发（无 Docker）
redis-server &                                    # 启动 Redis
cd backend && pip install -r requirements.txt      # 安装依赖
AUTH_MODE=browser COOKIES_FROM_BROWSER=edge uvicorn app.main:app --reload --port 8000  # API
python -m app.worker                               # Worker（另开终端，需在 backend/ 目录下）
cd frontend && python -m http.server 3000          # 前端静态服务

# Cookie 管理
./refresh_cookies.sh          # 从 Edge 提取
./refresh_cookies.sh chrome   # 从 Chrome 提取
```

访问地址：Docker 模式 `http://localhost:8080`，本地开发 `http://localhost:3000`。

## Architecture

```
浏览器 → Nginx (:8080) → FastAPI API (:8000) → Redis Queue → Worker (yt-dlp + ffmpeg)
```

### 请求流程

1. **解析**：前端 POST `/api/resolve` → `ytdlp_service.resolve_formats()` 调用 yt-dlp 提取视频格式列表，包括自动合成 DASH 合并选项（video+audio）
2. **下载**：前端 POST `/api/download` → `task_manager.create_task()` 创建 TaskInfo 写入 Redis 并推入 `queue:downloads` 队列
3. **执行**：Worker 从 Redis 队列 BRPOP 取任务 → 线程池执行 `_run_ytdlp()` → 进度通过 `_sync_progress` 协程每 2 秒写回 Redis
4. **轮询**：前端每 1.5 秒 GET `/api/tasks/:id` 查询进度
5. **取件**：任务完成后 GET `/api/files/:id` 下载文件，支持 HTTP Range 断点续传

### Key Design Decisions

- **API 和 Worker 是同一个 Docker 镜像、不同启动命令**：`api` 用 uvicorn 启动 FastAPI，`worker` 用 `python -m app.worker` 启动
- **yt-dlp 调用是同步阻塞的**：Worker 通过 `ThreadPoolExecutor` + `asyncio.run_in_executor` 包装，并发数由 `MAX_CONCURRENT_DOWNLOADS` 控制
- **任务重试**：Worker 区分可恢复错误（网络/超时）和不可恢复错误（视频不存在/版权/私有），后者立即终止
- **文件清理**：API 进程的 lifespan 中启动 `_cleanup_expired_files` 定时任务，按 `FILE_TTL_SECONDS` 清理过期下载目录
- **Cookie 认证**：生产用 `AUTH_MODE=cookies`（文件挂载），本地开发用 `AUTH_MODE=browser`（直接读浏览器）
- **URL 白名单**：`config.py` 中 `ALLOWED_HOSTS` 限制只接受 YouTube 域名
- **Nginx 限流**：resolve 接口 10r/m，download 接口 5r/m，IP 级别

### Redis Usage

- 任务数据：`task:{task_id}` → TaskInfo JSON，TTL 7200 秒
- 下载队列：`queue:downloads` → List，LPUSH 入队 / BRPOP 出队
- 使用 `redis.asyncio` 异步客户端，全局单例

## Tech Stack Details

- Python 3.12 / FastAPI / Pydantic v2 / uvicorn
- yt-dlp（YouTube 解析与下载）+ ffmpeg（音视频合并转码）+ Node.js（YouTube n-parameter 签名）
- Redis 7（任务队列 + 状态缓存）
- 前端：纯 HTML/CSS/JS 单页应用，无构建工具
- 所有配置通过环境变量驱动，定义在 `backend/app/config.py`
