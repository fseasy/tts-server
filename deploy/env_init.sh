#!/bin/bash
# This is used to install the dependency to the machine.
# It should be run only once in the machine
# run this file in the current dir.
# or use bash to run it.

set -e
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# install uv for python (only if not installed)
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    wget -qO- https://astral.sh/uv/install.sh | sh
else
    echo "uv already installed. Skipping."
fi

# install ffmpeg for audio validation (only if not installed) 
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    sudo apt install -y ffmpeg
else
    echo "ffmpeg already installed. Skipping."
fi

# install git (only if not installed)
if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    sudo apt install -y git
else
    echo "Git already installed. Skipping."
fi

# we assume 
# 1. nginx has already been installed
# 2. private repo that contains config file (used for `confgen/gen.py`) has already been cloned.
# Then **fill/change** the following ENV vars so we can then run the `project_init.sh`

ENV=prod
PROJECT_ROOT_LOCAL_DIR=/root/deploy/dajuan-english/docgate
VENV_BIN_DIR="$PROJECT_ROOT_LOCAL_DIR/.venv/bin"
DOCGATE_SRC_DIR="$PROJECT_ROOT_LOCAL_DIR/docgate"
CONF_SYNC_GIT_REPO_LOCAL_DIR=/root/github/private-conf/web/docgate/confgen
NGINX_SYSTEM_CONF_DIR=/etc/nginx/conf.d
SYSTEMD_SERVICE_NAME="docgate-fastapi"
PATH="$PATH:$HOME/.local/bin:$HOME/.local/share/pnpm" # for github workflow

cat > $SCRIPT_DIR/.env << EOF

ENV=$ENV
PROJECT_ROOT_LOCAL_DIR=$PROJECT_ROOT_LOCAL_DIR
CONF_SYNC_GIT_REPO_LOCAL_DIR=$CONF_SYNC_GIT_REPO_LOCAL_DIR
NGINX_SYSTEM_CONF_DIR=$NGINX_SYSTEM_CONF_DIR
SYSTEMD_SERVICE_NAME=$SYSTEMD_SERVICE_NAME
PATH=$PATH

EOF

# write the systemd service file.
cat > "$SCRIPT_DIR/$SYSTEMD_SERVICE_NAME.service" << EOF

[Unit]
Description=Docgate FastAPI App
After=network.target

[Service]
Type=notify
NotifyAccess=main
# NOTE: here I just set it to root. Change as your actual condition.
User=root
Group=root
WorkingDirectory=$DOCGATE_SRC_DIR
Environment="PATH=$VENV_BIN_DIR"
Environment="ENV=$ENV"
# Note: I set worker=1.
ExecStart=$VENV_BIN_DIR/gunicorn app:app \
  -k uvicorn.workers.UvicornWorker \
  -w 1 \
  --timeout 60 \
  -b 127.0.0.1:3001

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30

Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target

EOF