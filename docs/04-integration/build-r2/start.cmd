@echo off
rem 极境 ZenithLens · R2 开发版构建启动脚本（OpenCode · S5+C0+C1b+R3 终验 v7 · 2026-09-13）
rem 用法：双击本文件，或在终端执行 start.cmd [--port 8792]
cd /d "%~dp0"
python app.py %*
