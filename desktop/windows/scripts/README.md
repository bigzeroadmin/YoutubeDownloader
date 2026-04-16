# Windows Build Scripts (Placeholder)
# TODO: Implement Windows-specific build scripts

## Requirements

1. **Python 3.12** - Download from python-build-standalone for Windows x64
   - URL: https://github.com/indygreg/python-build-standalone/releases
   - File: cpython-3.12.x-windows-x64-install_only.tar.gz

2. **ffmpeg** - Download static build for Windows
   - URL: https://github.com/BtbN/FFmpeg-Builds/releases
   - File: ffmpeg-master-latest-win64-gpl.zip

3. **Node.js** - Download Windows binary
   - URL: https://nodejs.org/dist/v22.15.0/
   - File: node-v22.15.0-win-x64.zip

## Scripts to Create

- `scripts/download-binaries.ps1` - Download ffmpeg, node, python binaries
- `scripts/build-python-env.ps1` - Setup Python virtual environment with dependencies
