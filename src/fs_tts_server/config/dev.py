import logging

from .data_types import AppConf, Env

app_conf = AppConf(env=Env.DEV, app_domain="http://localhost", log_level=logging.DEBUG, auth_apikey="dev.fs-tts-server")
