# YouTube、TikTok & 抖音 Downloader Desktop

YouTube、TikTok 与抖音视频/音频下载桌面应用。支持 macOS 和 Windows。

## 功能特性

- **多平台解析** — 支持 YouTube、YouTube Music、TikTok、抖音视频及平台短链接
- **格式选择** — 列出所有可用的视频/音频格式（清晰度、编码、大小）
- **视频下载** — 支持 360p / 720p / 1080p / 4K 等各种清晰度
- **DASH 自动合并** — 视频流和音频流分离时，自动通过 ffmpeg 合并为 mp4
- **音频提取** — 支持导出 m4a 原始音频或转码为 mp3
- **实时进度** — 下载任务实时状态和进度跟踪
- **断点续传** — 中断后从已下载处继续

## 项目结构

```
desktop/
├── shared/                    # 公共代码
│   ├── backend/              # FastAPI 后端
│   └── frontend/             # 前端 HTML/CSS/JS
├── macos/                     # macOS 版本
│   ├── src/                  # Electron 主进程
│   ├── assets/               # 图标资源
│   ├── scripts/              # 构建脚本
│   ├── resources/            # Python/ffmpeg/node 二进制
│   ├── electron-builder.yml
│   └── package.json
├── windows/                   # Windows 版本
│   ├── src/                  # Electron 主进程
│   ├── scripts/              # 构建脚本（模板）
│   ├── electron-builder.yml
│   └── package.json
└── package.json              # 根配置（工作区）
```

## macOS 版本

### 开发环境要求

- Node.js 18+
- Python 3.12（用于后端）

### 开发模式

```bash
cd desktop
npm install
npm run macos
```

### 构建

```bash
cd desktop/macos
npm install
npm run prebuild    # 下载 Python/ffmpeg/node 二进制
npm run build       # 构建 DMG
```

构建产物在 `desktop/macos/dist/` 目录。

## Windows 版本

Windows 版本目前为框架模板，需要完善以下内容：

1. **下载二进制依赖** - 实现 `scripts/download-binaries.ps1`
2. **构建 Python 环境** - 实现 `scripts/build-python-env.ps1`
3. **准备图标** - 添加 `assets/icon.ico`

### 开发模式

```bash
cd desktop
npm install
npm run windows
```

### 构建

```bash
cd desktop/windows
npm install
npm run build
```

## 技术栈

| 组件 | 技术 | 用途 |
|---|---|---|
| 桌面框架 | Electron | 跨平台桌面应用 |
| 后端 API | Python / FastAPI | REST API 服务 |
| 下载引擎 | yt-dlp | YouTube/TikTok/抖音解析与下载 |
| 媒体处理 | ffmpeg | 音视频合并与转码 |
| JS 运行时 | Node.js | YouTube n-parameter 签名挑战 |
| 前端 | HTML / CSS / JS | 单页 Web 应用 |

## 许可证

仅限个人/内部使用。请遵守 YouTube、TikTok、抖音的使用条款和适用的版权法律。
