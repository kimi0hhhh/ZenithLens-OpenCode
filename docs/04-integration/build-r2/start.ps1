# 极境 ZenithLens · R2 开发版构建启动脚本（OpenCode · S5+C0+C1b+R3 终验 v7 · 2026-09-13）
# 用法：powershell -File start.ps1 [-port 8792]
Set-Location -LiteralPath $PSScriptRoot
python app.py @args
