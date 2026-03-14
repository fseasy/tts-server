#!/usr/bin/env bash
# run dev backend + frontend
set -euo pipefail

cleanup() {
  trap - EXIT INT TERM
  echo "Stopping all child processes..."
  pkill -P $$
}


ENV=dev uv run uvicorn fs_tts_server.main:app --reload --port 3101