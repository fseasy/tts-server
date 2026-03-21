#!/bin/bash
# This script can be run once the `env_init.sh` has been called and the dependency dir is prepared before
# it's also intended for updating project (pull latest & re-build & reload)

set -Eeuo pipefail
trap 'echo "❌ Error at line $LINENO: $BASH_COMMAND"; exit 1' ERR
set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# source env exported by env_init.sh
source $SCRIPT_DIR/.env

# check env
: "${ENV?env-var ENV is required}"
: "${PROJECT_ROOT_LOCAL_DIR?env-var PROJECT_ROOT_LOCAL_DIR is required}"
: "${CONF_SYNC_GIT_REPO_LOCAL_DIR?env-var CONF_SYNC_GIT_REPO_LOCAL_DIR is required}"
: "${NGINX_SYSTEM_CONF_DIR?env-var NGINX_SYSTEM_CONF_DIR is required}"
: "${SYSTEMD_SERVICE_NAME?env-var SYSTEMD_SERVICE_NAME is required}"


PROD_CONF_PROJECT_INSIDE_DIR="$PROJECT_ROOT_LOCAL_DIR/src/fs_tts_server/config"

# prepare conf from another private repo: 
# 1. enter the private repo to fetch the latest conf 2. link it to the project inside
echo "pull the config file ${ENV}.py from ${CONF_SYNC_GIT_REPO_LOCAL_DIR} git repo"
cd $CONF_SYNC_GIT_REPO_LOCAL_DIR
git pull
mkdir -p $PROD_CONF_PROJECT_INSIDE_DIR
ln -sn "$CONF_SYNC_GIT_REPO_LOCAL_DIR/${ENV}.py" "$PROD_CONF_PROJECT_INSIDE_DIR/${ENV}.py" || true # skip set -x
# go to workdir ROOT
cd $PROJECT_ROOT_LOCAL_DIR
echo "now switch to release branch"
# 1. switch to release branch
git fetch origin --prune
git checkout release
git reset --hard origin/release
# 2. prepare uv env
## it will create env, install dependency (without dev group). it'll also install self as editable package
uv sync --frozen --no-dev  # --frozen 保证不修改 lock 文件，--no-dev 只装生产依赖

# 3. link nginx conf
echo "Link nginx conf"
ln -sn "$CONF_SYNC_GIT_REPO_LOCAL_DIR/nginx.${ENV}.conf" "$NGINX_SYSTEM_CONF_DIR/tts-server.conf" || true

# 4. install gunicorn services for fastapi
service_fname="${SYSTEMD_SERVICE_NAME}.service"
service_target_fpath="/etc/systemd/system/${service_fname}"
service_source_fpath="${SCRIPT_DIR}/${service_fname}"
echo "Deploying systemd service: ${SYSTEMD_SERVICE_NAME}"

if [ ! -f "$service_target_fpath" ]; then
# ---------- First install ----------
  echo "Service not found → installing"
  sudo install -m 644 \
    "$service_source_fpath" \
    "$service_target_fpath"
  echo "Reloading systemd daemon"
  sudo systemctl daemon-reload
  echo "Enabling service"
  sudo systemctl enable "$SYSTEMD_SERVICE_NAME"
  echo "Starting service"
  sudo systemctl start "$SYSTEMD_SERVICE_NAME"
else
# ---------- Update ----------
  if cmp -s "$service_source_fpath" "$service_target_fpath"; then
    echo "Service file unchanged → reload service"
    sudo systemctl reload "$SYSTEMD_SERVICE_NAME"
  else
    echo "Service file changed → restart service"
    sudo install -m 644 \
      "$service_source_fpath" \
      "$service_target_fpath"
    echo "Reloading systemd daemon"
    sudo systemctl daemon-reload
    echo "Restarting service"
    sudo systemctl restart "$SYSTEMD_SERVICE_NAME"
  fi
fi
echo "Service status:"
sudo systemctl --no-pager --full status "$SYSTEMD_SERVICE_NAME"

echo "Test Nginx config & Restart Nginx"
# 4. restart nginx
nginx -t
systemctl restart nginx

echo "All done"