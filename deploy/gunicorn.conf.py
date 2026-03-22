# see https://gunicorn.org/reference/settings/#config

from fs_pyutils.systemd_notifier import intercept_server_ready_signal

# --- Gunicorn 配置 ---
bind = "127.0.0.1:6001"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
loglevel = "info"
logger_class = "fs_pyutils.gunicorn_logger.GunicornSyslogLogger"

# intercept ready signal
intercept_server_ready_signal()


def on_starting(server):
  """
  Gunicorn Master 启动前的钩子
  此时 Gunicorn 发现环境变量里没有 NOTIFY_SOCKET，它就会变回 'simple' 模式的行为
  """
  server.log.info("Systemd NOTIFY_SOCKET intercepted. Manual notification enabled.")


# 你也可以在这里配置其他钩子，比如 worker 退出时的逻辑
