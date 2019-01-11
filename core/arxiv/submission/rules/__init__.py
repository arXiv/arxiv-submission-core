from .base import should_apply_rules, apply, execute_callback, set_save_func
from .set_title import *

from .celery import execute_async, register_async, get_or_create_worker_app

register_async(execute_callback)
