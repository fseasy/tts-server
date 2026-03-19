#!/usr/bin/env bash
# run dev backend + frontend
set -euo pipefail

cleanup() {
  trap - EXIT INT TERM
  echo "Stopping all child processes..."
  pkill -P $$
}


# ENV=dev uv run uvicorn fs_tts_server.main:app --reload --port 6001
export ENV=dev
export SYSLOG_ADDRESS="127.0.0.1:11514"
export HOSTNAME="local_tts_server"

uv run gunicorn fs_tts_server.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 1 \
  --timeout 60 \
  -b 127.0.0.1:6001 \
  --logger-class fs_pyutils.gunicorn_logger.GunicornSyslogLogger \
  --log-level info
