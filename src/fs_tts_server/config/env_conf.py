"""A tool for special condition"""

from .data_types import AppConf, Env


def get_env_conf(env: Env) -> AppConf:
  if env == Env.DEV:
    from .dev import app_conf

    return app_conf
  elif env == Env.PROD:
    from .prod import app_conf

    return app_conf
  assert f"Invalid env: {env}"
