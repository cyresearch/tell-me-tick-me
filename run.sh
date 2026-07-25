#!/usr/bin/env bash
# tellmetickme 启动脚本。默认读 data/todo.md (首跑自动生成示例), 归档到 data/daily/。
# 手机局域网访问: DESK_BIND=0.0.0.0 ./run.sh  然后手机开 http://<mini局域网IP>:8765
set -euo pipefail
cd "$(dirname "$0")"
export DESK_PORT="${DESK_PORT:-8765}"
export DESK_BIND="${DESK_BIND:-127.0.0.1}"
exec python3 server.py
