#!/bin/bash
# * A common utils for deploy.
# * version: 1.0.0
set -Eeuo pipefail

# * 将 src link 到 tgt 位置，可以给定多个待测试的 src，找到第一个存在的，用于 link.
# * link 时会做检查，
# * 1. 如果 tgt 位置已经存在内容，且根本不是 link, 这时说明不需要 link (因为有时一些内容已经在仓库中存在，不需要 link 引入)，直接返回
# * 2. 如果路径完全相同，就跳过（已经 link 过了）
# * link 时自动判断是否需要加 sudo, 但也可以通过设置 ENV-VAR: USE_SUDO=true 来强制指定 sudo, 一般不必要
# * 参数 1: link_target (最终生成的软链路径) 注意，如果是 link 一个文件，那么这里必须也写成文件，而不是省略表文件名只写 dir
# *        因为内部会判断 link_target 是否是非 link, 如果写 dir，这里直接退出了，与目标相反
# * 参数 2 及以后: link_src_candidates (候选源文件路径列表, 可以多个)
# --- 使用方式示例 ---
# - 注意 link-target 必须写到文件级别
# >>> safe_ln_test_and_link "/etc/nginx/conf.d/test.conf" "./my-nginx.conf" "$PRIVATE_DIR/my-nginx.conf"

safe_ln_test_and_link() {
	local target_path="$1"
	shift
	local src_candidates=("$@")
	local final_src=""

	# --- 安全检查逻辑：如果目标路径已存在，且它【不是】一个符号链接 (Symlink) ---
	# 这意味着它可能是一个真实的文件或目录，不能随便覆盖
	if [[ -e "$target_path" && ! -L "$target_path" ]]; then
		echo "Link note: Target '$target_path' already exists and is a REAL FILE/DIR (not a symlink). SKIP LINK."
		return 0
	fi

	# 1. 寻找第一个存在的源文件
	for src in "${src_candidates[@]}"; do
		if [[ -e "$src" ]]; then
			final_src="$src"
			break
		fi
	done

	if [[ -z "$final_src" ]]; then
		echo "Error: No valid source file found in candidates: [${src_candidates[*]}]"
		return 1
	fi

	# 2. 规范化路径以进行比较 (获取绝对物理路径)
	local abs_src=$(readlink -f "$final_src")
	local abs_target=""
	[[ -e "$target_path" || -L "$target_path" ]] && abs_target=$(readlink -f "$target_path")

	# 3. 幂等性检查：如果已经指向同一个地方，直接退出
	if [[ "$abs_src" == "$abs_target" ]]; then
		echo "Skip: '$target_path' already linked to '$abs_src'."
		return 0
	fi

	# 4. 自动处理 Sudo
	# 逻辑：如果是 root 用户，或者对目标父目录有写权限，则不加 sudo；否则加 sudo
	local cmd_prefix=""
	local target_dir=$(dirname "$target_path")

	# 检查是否需要 sudo:
	# 不是 root (UID 0) 且 对目标目录没有写权限
	if [[ "${USE_SUDO:-false}" == "true" ]] || ([[ $EUID -ne 0 ]] && [[ ! -w "$target_dir" ]]); then
		cmd_prefix="sudo"
	fi

	# 5. 执行创建/更新链接
	echo "Linking: $final_src -> $target_path (via ${cmd_prefix:-direct})"
	$cmd_prefix ln -snf "$final_src" "$target_path"
}

# * 进入到 repo dir 并切换到对应 branch 后同步代码
# * 参数 1：repo 目录
# * 参数 2：分支名
git_update_to_branch() {
	local repo_dir="$1"
	local branch="$2"

	echo "--- Updating Git Repo: $repo_dir to branch [$branch] ---"

	# 使用 pushd 并静默输出
	# 如果目录不存在，pushd 会返回非零，set -e 会直接让脚本在此退出，非常安全
	pushd "$repo_dir" >/dev/null

	# 这里的每一行如果失败，都会因为 set -e 直接中断脚本并报错
	git fetch origin --prune
	git checkout "$branch"
	git reset --hard "origin/$branch"

	# 回到原目录
	popd >/dev/null

	echo "✅ Successfully updated to origin/$branch"
}

# * 通用校验函数：检查 $1 是否在 [$2, $3, ...] 之中
# * 用法: is_in_list "欲检查的值" "候选1" "候选2" "候选3"
is_in_list() {
	local search="$1"
	shift
	local list=("$@")

	for item in "${list[@]}"; do
		if [[ "$item" == "$search" ]]; then
			return 0 # 找到了，返回成功
		fi
	done
	return 1 # 没找到，返回失败
}

# * deploy gunicorn systemd service.
# * Args 1：service file path，ASSERT: the file path/name must end with `.service`
# Example: deploy_gunicorn_systemd_service ./deploy/gunicorn_api.service
deploy_gunicorn_systemd_service() {
	local source_fpath="$1"

	# 1. check arg
	if [[ -z "$source_fpath" ]]; then
		echo "Usage: deploy_systemd_service <path/to/service_file>"
		return 1
	fi

	if [[ ! -f "$source_fpath" ]]; then
		echo "Error: Source file '$source_fpath' not found."
		return 1
	fi

	# 2. extract the service-name.
	local service_fname=$(basename "$source_fpath")
	local service_name="${service_fname%.service}"
	local target_fpath="/etc/systemd/system/${service_fname}"

	# service name suffix check
	if [[ "$service_fname" != *.service ]]; then
		echo "Error: File '$source_fpath' must have a .service extension."
		return 1
	fi

	echo "--- Managing systemd service: ${service_name} ---"

	# systemd-analyze verify syntax correction
	if ! systemd-analyze verify "$source_fpath" >/dev/null 2>&1; then
		echo "Error: Service file '$source_fpath' failed syntax verification."
		echo "Hint: Run 'systemd-analyze verify $source_fpath' to see details."
		return 1
	fi
	echo "✓ Syntax verification passed."

	# Install/update
	if [ ! -f "$target_fpath" ]; then
		# ---------- Install ----------
		echo "Status: New service detected → Installing..."
		sudo install -m 644 "$source_fpath" "$target_fpath"
		sudo systemctl daemon-reload
		sudo systemctl enable "$service_name"
		sudo systemctl start "$service_name"
	else
		# ---------- Update ----------
		if cmp -s "$source_fpath" "$target_fpath"; then
			# reload when no service file no change
			echo "Status: Config unchanged → Reload service or restarting..."
			# try to reload when service has `ExecReload=`
			sudo systemctl reload "$service_name" 2>/dev/null || sudo systemctl restart "$service_name"
		else
			# config changed.
			echo "Status: Config changed → Updating and Restarting..."
			sudo install -m 644 "$source_fpath" "$target_fpath"
			sudo systemctl daemon-reload
			sudo systemctl restart "$service_name"
		fi
	fi

	# 5. check results
	echo "Waiting for $service_name to become active..."
	timeout=120
	while [ $timeout -gt 0 ]; do
		if sudo systemctl is-active --quiet "$service_name"; then
			echo -e "\nResult: $service_name is successfully running. ✅"
			break
		else
			# \r 让光标回到行首，-n 确保不换行
			echo -ne "\rWaiting for $service_name... (Timeout remaining: ${timeout}s)   "
			sleep 5
			timeout=$((timeout - 5))
		fi
	done

	if sudo systemctl is-active --quiet "$service_name"; then
		echo "Service status:"
		sudo systemctl --no-pager --full status "$service_name"
	else
		echo "Result: $service_name failed to start. Check 'journalctl -u $service_name' for logs."
		return 1
	fi

}
