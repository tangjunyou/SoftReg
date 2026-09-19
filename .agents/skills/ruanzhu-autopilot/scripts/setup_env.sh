#!/usr/bin/env bash
# 软著 autopilot 环境准备：项目根创建 .venv 并安装依赖。
# 以调用者的当前工作目录为项目根（用户项目在哪，venv 就建在哪）
set -euo pipefail

ROOT="$PWD"

if [ ! -d .venv ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1; then
      V="$("$c" -c 'import sys; print(sys.version_info >= (3, 10) and "1" or "0")')"
      if [ "$V" = "1" ]; then PY="$c"; break; fi
    fi
  done
  if [ -z "$PY" ]; then
    echo "STOP_FOR_USER"
    echo "NEXT_ACTION: 未找到 Python 3.10+，请安装后重试（macOS: brew install python@3.12）。"
    exit 1
  fi
  "$PY" -m venv .venv
fi

.venv/bin/pip install --quiet --disable-pip-version-check reportlab pypdfium2 pillow pypdf
.venv/bin/python - <<'EOF'
import reportlab, pypdfium2, PIL
from pathlib import Path
print("deps OK | reportlab", reportlab.Version)
for kind, paths in {
    "mono": ["/System/Library/Fonts/Supplemental/Courier New.ttf"],
    "cjk": ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf"],
}.items():
    hit = next((p for p in paths if Path(p).exists()), None)
    print(f"font {kind}:", hit or "MISSING (Linux 用户请安装任一等宽+CJK字体)")
EOF
echo "环境就绪：$ROOT/.venv"
