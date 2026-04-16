# YouTube Downloader

YouTube 视频/音频下载工具。支持 Docker 一键部署。

## 功能特性

- **格式选择** — 解析 YouTube 链接，列出所有可用的视频/音频格式（清晰度、编码、大小）
- **视频下载** — 支持 360p / 720p / 1080p / 4K 等各种清晰度
- **DASH 自动合并** — 视频流和音频流分离时，自动通过 ffmpeg 合并为 mp4
- **音频提取** — 支持导出 m4a 原始音频或转码为 mp3
- **异步任务队列** — Redis 驱动的后台下载队列，实时进度跟踪，支持多任务并行下载
- **下载队列面板** — 页面底部显示所有下载任务的实时状态、进度和下载链接
- **大文件支持** — 超过 2GB 的文件自动使用更长超时（默认 2 小时），避免下载中断
- **Cookie 自动恢复** — 下载过程中 cookie 失效时，Worker 自动等待 cron 刷新 cookie 后断点续传
- **断点续传** — yt-dlp 层保留 .part 文件，中断后从已下载处继续；文件下载接口支持 HTTP Range
- **自动重试** — 网络错误、超时等可恢复故障自动重试（指数退避），不可恢复错误（视频不存在等）立即终止
- **文件自动清理** — 下载完成的文件按 TTL 过期自动删除，避免磁盘占满

## 系统架构

```
浏览器 → Nginx (:8080) → FastAPI API → Redis Queue → Worker (yt-dlp + ffmpeg)
                                ↕                         ↕
                          任务状态查询              本地临时存储
                                ↕
                          文件下载 (Range 支持)
```

### 项目结构

```
YoutubeDownload/
├── backend/
│   ├── app/
│   │   ├── config.py              # 全局配置（环境变量驱动）
│   │   ├── models.py              # Pydantic 数据模型
│   │   ├── main.py                # FastAPI 入口 + 文件清理定时任务
│   │   ├── worker.py              # 异步下载 Worker（线程池 + 进度同步）
│   │   ├── routes/
│   │   │   ├── auth.py            # GET  /api/auth/status
│   │   │   ├── cookies.py         # GET  /api/cookies/status
│   │   │   ├── resolve.py         # POST /api/resolve
│   │   │   ├── download.py        # POST /api/download
│   │   │   ├── tasks.py           # GET  /api/tasks/:id
│   │   │   └── files.py           # GET  /api/files/:id (Range 支持)
│   │   └── services/
│   │       ├── ytdlp_service.py   # yt-dlp 封装（解析 + cookies + JS runtime）
│   │       ├── task_manager.py    # Redis 任务队列 CRUD
│   │       └── cookie_refresh.py  # Cookie 刷新等待（mtime 轮询）
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html                 # 单页应用
│   ├── style.css                  # 暗色主题 UI
│   └── app.js                     # 前端交互逻辑（多任务队列）
├── nginx/
│   └── nginx.conf                 # 反向代理 + 限流 + 动态 DNS
├── docker-compose.yml             # 四个服务：Redis / API / Worker / Nginx
├── refresh_cookies.sh             # Cookie 自动提取脚本
├── .env.example                   # 环境变量模板
└── .gitignore
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- 宿主机安装 yt-dlp（用于提取浏览器 cookies）
- 浏览器（Edge / Chrome / Firefox）已登录 YouTube

### 第一步：安装 yt-dlp（宿主机）

```bash
pip3 install yt-dlp
```

### 第二步：提取 YouTube Cookies

```bash
./refresh_cookies.sh          # 默认从 Edge 提取
./refresh_cookies.sh chrome   # 从 Chrome 提取
./refresh_cookies.sh firefox  # 从 Firefox 提取
```

脚本会自动从浏览器读取 YouTube cookies 并写入 `cookies.txt`，无需安装任何浏览器扩展。

> **为什么需要 Cookies？** YouTube 会对非浏览器请求进行 bot 检测，需要携带有效的登录 cookies 才能获取视频格式列表。

### 第三步：启动服务

```bash
docker compose up -d --build
```

### 第四步：打开应用

浏览器访问 **http://localhost:8080**

粘贴 YouTube 链接 → 选择格式 → 点击下载按钮。页面底部会显示所有下载任务的实时进度。

### 停止服务

```bash
docker compose down
```

## Cookie 管理

### 自动刷新（推荐）

设置 cron 定时任务，定期从浏览器提取最新 cookies。建议每 30 分钟刷新一次，这样大文件下载过程中 cookie 失效时，Worker 能自动等待到下一次刷新后恢复下载：

```bash
crontab -e
```

添加以下内容（将路径替换为实际路径）：

```
*/30 * * * * /path/to/YoutubeDownload/refresh_cookies.sh edge >> /tmp/cookie_refresh.log 2>&1
```

cookies.txt 通过 bind mount 挂载到容器，更新后无需重启服务。

> **大文件下载与 Cookie 刷新**：下载超过 2GB 的高清视频时，Worker 会自动使用 2 小时超时。如果下载过程中 cookie 失效，Worker 会进入 `waiting_cookies` 状态，每 5 秒检查一次 cookie 文件是否被 cron 更新。检测到更新后自动断点续传，无需手动干预。

### 手动导出（备选）

如果自动提取脚本不适用你的环境：

1. 安装浏览器扩展 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)（Edge/Chrome 通用）
2. 访问 [youtube.com](https://www.youtube.com) 并确保已登录
3. 用扩展导出 cookies（Netscape 格式），保存为项目根目录的 `cookies.txt`

### 检查 Cookie 状态

```bash
# 基础认证状态
curl http://localhost:8080/api/auth/status

# 详细 Cookie 状态（含年龄和新鲜度）
curl http://localhost:8080/api/cookies/status
```

返回示例：

```json
{
  "auth_mode": "cookies",
  "cookies_file": "/app/cookies.txt",
  "cookie_count": 23,
  "ready": true,
  "age_seconds": 1200,
  "max_age_seconds": 3600,
  "is_fresh": true
}
```

## 本地开发（不用 Docker）

```bash
# 启动 Redis
redis-server &

# 安装依赖
cd backend
pip install -r requirements.txt

# 设置从浏览器直接读取 cookies（无需 cookies.txt）
export AUTH_MODE=browser
export COOKIES_FROM_BROWSER=edge

# 启动 API 服务
uvicorn app.main:app --reload --port 8000

# 另开终端，启动 Worker
cd backend
python -m app.worker

# 另开终端，启动前端
cd frontend
python -m http.server 3000
```

访问 `http://localhost:3000`，前端会自动请求 `/api` 路径。

## API 文档

### 认证状态

```
GET /api/auth/status
```

返回当前认证模式和 cookies 状态。

### Cookie 状态

```
GET /api/cookies/status
```

返回 Cookie 详细状态，包括文件年龄（秒）和是否在有效期内。

### 解析视频格式

```
POST /api/resolve
Content-Type: application/json

{ "url": "https://www.youtube.com/watch?v=VIDEO_ID" }
```

返回视频标题、缩略图、时长和所有可用格式列表（包括自动合成的 DASH 合并选项）。

### 创建下载任务

```
POST /api/download
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "format_id": "137+251",
  "audio_only": false,
  "convert_mp3": false,
  "expected_filesize": 5368709120
}
```

| 参数 | 类型 | 说明 |
|---|---|---|
| `url` | string | YouTube 视频链接 |
| `format_id` | string | 格式 ID（从 resolve 接口获取，合并格式如 `137+251`） |
| `audio_only` | bool | 仅下载音频（使用 bestaudio） |
| `convert_mp3` | bool | 转码为 MP3（192kbps） |
| `expected_filesize` | int \| null | 预计文件大小（字节），用于自动调整下载超时 |

返回 `task_id` 用于查询进度。

### 查询任务状态

```
GET /api/tasks/:task_id
```

返回示例：

```json
{
  "task_id": "abc123",
  "status": "running",
  "progress": 45.2,
  "retries": 0,
  "cookie_retries": 0,
  "filename": null,
  "error": null
}
```

任务状态：`pending` → `running` → `success` / `failed`

Cookie 失效时：`running` → `waiting_cookies` → `pending` → `running`（自动恢复）

### 下载文件

```
GET /api/files/:task_id
```

支持 HTTP Range 请求（断点续传）。任务状态为 `success` 时可用。

## 配置参数

所有参数通过环境变量配置，可在 `docker-compose.yml` 或 `.env` 文件中设置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接地址 |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Worker 最大并发下载数 |
| `RESOLVE_TIMEOUT_SECONDS` | `30` | 视频信息解析超时（秒） |
| `DOWNLOAD_TIMEOUT_SECONDS` | `600` | 单个下载任务超时（秒） |
| `LARGE_FILE_TIMEOUT_SECONDS` | `7200` | 大文件下载超时（秒），当文件超过阈值时使用 |
| `LARGE_FILE_THRESHOLD_BYTES` | `2147483648` | 大文件阈值（字节），默认 2GB |
| `FILE_TTL_SECONDS` | `3600` | 下载文件保留时间（秒），过期自动删除 |
| `CLEANUP_INTERVAL_SECONDS` | `300` | 过期文件扫描间隔（秒） |
| `WORKER_MAX_RETRIES` | `3` | 任务级最大重试次数（网络错误等） |
| `WORKER_RETRY_DELAY_SECONDS` | `5` | 重试基础延迟（指数退避） |
| `COOKIE_MAX_AGE_SECONDS` | `3600` | Cookie 新鲜度阈值（秒），超过此值视为过期 |
| `COOKIE_REFRESH_WAIT_SECONDS` | `120` | Cookie 失效后等待刷新的最长时间（秒） |
| `COOKIE_RETRY_MAX` | `2` | Cookie 失效后最大重试次数 |
| `AUTH_MODE` | `cookies` | 认证方式：`cookies`（文件）/ `browser`（本地开发） |
| `COOKIES_FILE` | (空) | cookies.txt 文件路径 |
| `COOKIES_FROM_BROWSER` | (空) | 浏览器名称（仅 `browser` 模式） |

## Docker 代理配置

如果你的网络环境需要代理才能访问 YouTube，在 `docker-compose.yml` 的 `api` 和 `worker` 服务中添加环境变量：

```yaml
environment:
  HTTP_PROXY: http://host.docker.internal:7890
  HTTPS_PROXY: http://host.docker.internal:7890
  NO_PROXY: localhost,127.0.0.1,redis
```

- `host.docker.internal` 指向宿主机（Docker Desktop 内置）
- 端口替换为你的代理端口（Clash 默认 7890）
- 确保代理软件开启了「允许局域网连接」

## 常见问题

### 解析失败：Sign in to confirm you're not a bot

Cookies 失效或未配置。重新运行：

```bash
./refresh_cookies.sh
```

### 解析失败：n challenge solving failed

容器内缺少 JS 运行时。确认 Dockerfile 中已安装 `nodejs`（默认已包含）。

### 无可用格式（只有 storyboard）

通常是 cookies 问题。检查：

```bash
curl http://localhost:8080/api/cookies/status
```

如果 `cookie_count` 为 0 或 `is_fresh` 为 false，重新提取 cookies。

### 大文件下载中断 / Cookie 过期

确保已配置 cron 定期刷新 cookies：

```bash
*/30 * * * * /path/to/YoutubeDownload/refresh_cookies.sh edge >> /tmp/cookie_refresh.log 2>&1
```

Worker 检测到 cookie 失效后会进入 `waiting_cookies` 状态，等待 cron 刷新 cookie 文件后自动恢复断点续传（最长等待 `COOKIE_REFRESH_WAIT_SECONDS` 秒）。

如果下载超时，可调大 `LARGE_FILE_TIMEOUT_SECONDS`：

```yaml
environment:
  LARGE_FILE_TIMEOUT_SECONDS: "14400"  # 4 小时
```

### 502 Bad Gateway

API 容器未就绪或重启中。等待几秒后刷新，或检查：

```bash
docker compose logs api --tail 20
```

### 下载超时

普通文件默认超时 600 秒，超过 2GB 的文件自动使用 7200 秒。如果仍不够，调大相应参数：

```yaml
environment:
  DOWNLOAD_TIMEOUT_SECONDS: "1800"       # 普通文件 30 分钟
  LARGE_FILE_TIMEOUT_SECONDS: "14400"    # 大文件 4 小时
```

## 技术栈

| 组件 | 技术 | 用途 |
|---|---|---|
| 后端 API | Python / FastAPI | REST API 服务 |
| 下载引擎 | yt-dlp | YouTube 解析与下载 |
| 媒体处理 | ffmpeg | 音视频合并与转码 |
| JS 运行时 | Node.js | YouTube n-parameter 签名挑战 |
| 任务队列 | Redis | 任务调度与状态缓存 |
| 反向代理 | Nginx | 限流、静态文件、代理转发 |
| 前端 | HTML / CSS / JS | 单页 Web 应用 |
| 容器化 | Docker Compose | 一键部署四个服务 |

## 许可证

仅限个人/内部使用。请遵守 YouTube 使用条款和适用的版权法律。
