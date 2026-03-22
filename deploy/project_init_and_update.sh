#!/bin/bash
# This script can be run once the `env_init.sh` has been called and the dependency dir is prepared before
# it's also intended for updating project (pull latest & re-build & reload)

set -Eeuo pipefail
trap 'echo "❌ Error at line $LINENO: $BASH_COMMAND"; exit 1' ERR
# set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# source env exported by env_init.sh
source $SCRIPT_DIR/.env
source $SCRIPT_DIR/utils.sh

#! -------- Args ---------
# 定义 mode 的所有合法候选值
VALID_MODES=(
	"deving"  # 本地开发调试模式（不会强制切分支，可以本地修改+调试运行）
	"serving" # 线上服务模式
)

MODE=""

# --- 帮助信息 ---
usage() {
	echo "Usage: $0 --mode {${VALID_MODES[*]}}"
	exit 1
}

# --- 参数解析 ---
while [[ $# -gt 0 ]]; do
	case "$1" in
	--mode)
		# 获取参数值（确保 $2 存在）
		val="${2:-}"

		# 调用通用函数校验：把值传进去，再把整个候选数组传进去
		if is_in_list "$val" "${VALID_MODES[@]}"; then
			MODE="$val"
			shift 2
		else
			echo "❌ Error: Invalid mode '$val'. Expected one of: [${VALID_MODES[*]}]"
			usage
		fi
		;;
	*)
		usage
		;;
	esac
done

# 最后检查必填项
[[ -z "$MODE" ]] && {
	echo "❌ Error: --mode is required"
	usage
}

echo "🚀 Starting in $MODE mode..."

#! ------- Logic start ----------

# check env
: "${ENV?env-var ENV is required}"
: "${PROJECT_ROOT_LOCAL_DIR?env-var PROJECT_ROOT_LOCAL_DIR is required}"
: "${CONF_SYNC_GIT_REPO_LOCAL_DIR?env-var CONF_SYNC_GIT_REPO_LOCAL_DIR is required}"
: "${NGINX_SYSTEM_CONF_DIR?env-var NGINX_SYSTEM_CONF_DIR is required}"
: "${SYSTEMD_SERVICE_NAME?env-var SYSTEMD_SERVICE_NAME is required}"

#! 1. update project root dir & setup env by uv
cd $PROJECT_ROOT_LOCAL_DIR
# - force checkout to latest branch
git_update_to_branch $PROJECT_ROOT_LOCAL_DIR "release"
# - prepare uv env
## it will create env, install dependency (without dev group). it'll also install self as editable package
uv sync --frozen --no-dev # --frozen 保证不修改 lock 文件，--no-dev 只装生产依赖

#! 2. prepare conf from another private repo:
# enter the private repo to fetch the latest conf 2. link it to the project inside
echo "pull the config file ${ENV}.py from ${CONF_SYNC_GIT_REPO_LOCAL_DIR} git repo"
git_update_to_branch $CONF_SYNC_GIT_REPO_LOCAL_DIR "main"
PROD_CONF_PROJECT_INSIDE_DIR="$PROJECT_ROOT_LOCAL_DIR/src/fs_tts_server/config"
mkdir -p $PROD_CONF_PROJECT_INSIDE_DIR
safe_ln_test_and_link "$PROD_CONF_PROJECT_INSIDE_DIR/${ENV}.py" "$CONF_SYNC_GIT_REPO_LOCAL_DIR/${ENV}.py"

#! 3. install/update gunicorn services for fastapi, start/reload/restart services
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

#! 4. restart nginx
echo "Nginx: Link conf & Test config & Restart"
_args=(
	"$NGINX_SYSTEM_CONF_DIR/tts-server.conf"          # tgt
	"$CONF_SYNC_GIT_REPO_LOCAL_DIR/nginx.${ENV}.conf" # test-src1: private conf dir
	"$SCRIPT_DIR/nginx.${ENV}.conf"                   # test-src2: local conf dir
)
safe_ln_test_and_link "${_args[@]}"
sudo nginx -t
sudo systemctl restart nginx

echo "All done"
