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
    wget -qO- https://astral.sh/uv/install.sh | sh # => in `$HOME/.local/bin`
else
    echo "uv already installed. Skipping."
fi

# install ffmpeg for audio validation (only if not installed) 
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    sudo apt install -y ffmpeg # => in `usr/bin/`
else
    echo "ffmpeg already installed. Skipping."
fi

# install git (only if not installed)
if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    sudo apt install -y git # in `usr/bin/`
else
    echo "Git already installed. Skipping."
fi

# we assume 
# 1. nginx has already been installed
# 2. private repo that contains config file (used for config loading) has already been cloned.
# Then **fill/change** the following ENV vars so we can then run the `project_init.sh`

ENV=prod
PROJECT_ROOT_LOCAL_DIR=/root/deploy/tts-server
CONF_SYNC_GIT_REPO_LOCAL_DIR=/root/github/private-conf/web/tts-server/config
NGINX_SYSTEM_CONF_DIR=/etc/nginx/conf.d
SYSTEMD_SERVICE_NAME="tts-server-fastapi"
PATH="$HOME/.local/bin:$PATH" # for systemctl (looks like useless as the ExecStart need the absolute path)

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
Description=TTS-Server FastAPI App
After=network.target

[Service]
Type=simple # change to simple as LLM suggesting
# NOTE: here I just set it to root. Change as your actual condition.
User=root
Group=root
WorkingDirectory=$PROJECT_ROOT_LOCAL_DIR
Environment="PATH=$PATH"
Environment="ENV=$ENV"
# Note: I set worker=1.
ExecStart=$(which uv) run gunicorn fs_tts_server.main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 1 \
  --timeout 60 \
  -b 127.0.0.1:6001

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30

Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target

EOF