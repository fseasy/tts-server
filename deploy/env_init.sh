#!/bin/bash
# This is used to install the dependency to the machine.
# It should be run only once in the machine
# run this file in the current dir.
# or use bash to run it.

set -Eeuo pipefail
trap 'echo "❌ Error at line $LINENO: $BASH_COMMAND"; exit 1' ERR
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT_LOCAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# for ssh-login execution in github workflows (non-login shell)
# Add $PATH (Very important, or the following tools will be install once again due to it's not in non-login shell path)
export PATH="$HOME/.local/bin:$PATH"

# install uv for python (only if not installed)
if ! command -v uv &>/dev/null; then
	echo "Installing uv..."
	wget -qO- https://astral.sh/uv/install.sh | sh # => in `$HOME/.local/bin`
else
	echo "uv already installed. Skipping."
fi

# install ffmpeg for audio validation (only if not installed)
if ! command -v ffmpeg &>/dev/null; then
	echo "Installing ffmpeg..."
	sudo apt install -y ffmpeg # => in `usr/bin/`
else
	echo "ffmpeg already installed. Skipping."
fi

# install git (only if not installed)
if ! command -v git &>/dev/null; then
	echo "Installing Git..."
	sudo apt install -y git # in `usr/bin/`
else
	echo "Git already installed. Skipping."
fi

# we assume
# 1. nginx has already been installed
# 2. private repo that contains config file (used for config loading) has already been cloned.
# Then **fill/change** the following ENV vars so we can then run the `project_init.sh`

SYSTEMD_SERVICE_FILE_NAME="tts-server-fastapi.service"
GUNICORN_BIN_PATH="${PROJECT_ROOT_LOCAL_DIR}/.venv/bin/gunicorn"

# 如果存在 .machine.env，则引入它
# 注意：即使文件里定义了变量，也会被后续逻辑判断是否保留
if [ -f "$SCRIPT_DIR/.machine.env" ]; then
	source "$SCRIPT_DIR/.machine.env"
fi

# 3. 使用 : "${VAR:=DEFAULT}" 语法: 如果变量未设置或为空，则赋值为等号后面的默认值
: "${ENV:="prod"}"
: "${NGINX_SYSTEM_CONF_DIR:="/etc/nginx/conf.d"}"
# following 3 are required by GunicornSyslogLogger
: "${SYSLOG_ADDRESS:="127.0.0.1:11514"}"
: "${SYSLOG_HOSTNAME:="tts.fastapi"}"
: "${SYSLOG_TAG:="tts_fastapi"}"

cat >$SCRIPT_DIR/.env <<EOF

ENV="$ENV"
PROJECT_ROOT_LOCAL_DIR="$PROJECT_ROOT_LOCAL_DIR"
NGINX_SYSTEM_CONF_DIR="$NGINX_SYSTEM_CONF_DIR"
SYSTEMD_SERVICE_FILE_NAME="$SYSTEMD_SERVICE_FILE_NAME"
PATH="$PATH"

EOF

# write the systemd service file.
cat >"$SCRIPT_DIR/$SYSTEMD_SERVICE_FILE_NAME" <<EOF

[Unit]
Description=TTS-Server FastAPI App
After=network.target

[Service]
Type=notify
NotifyAccess=all

User=www-service
Group=www-service
WorkingDirectory=$PROJECT_ROOT_LOCAL_DIR
Environment="PATH=$PATH"
Environment="ENV=$ENV"
# required by gunicorn & fastapi service logger
Environment="SYSLOG_ADDRESS=$SYSLOG_ADDRESS"
Environment="SYSLOG_HOSTNAME=$SYSLOG_HOSTNAME"
Environment="SYSLOG_TAG=$SYSLOG_TAG"
# Note: I set worker=1.
# It's better to directly use gunicorn instead of use 'uv run gunicorn'
# as the main process need to interact with the systemd
ExecStart=${GUNICORN_BIN_PATH} \\
  -c file:${PROJECT_ROOT_LOCAL_DIR}/deploy/gunicorn.conf.py \\
  fs_tts_server.main:app \\

ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed

WatchdogSec=45
RestartSec=10
TimeoutStopSec=30
Restart=always

[Install]
WantedBy=multi-user.target

EOF
