"""Web Server Gateway Interface entry-point."""

import os
from typing import Optional

from flask import Flask

from filesystem.factory import create_app

__app__: Optional[Flask] = None


def application(environ, start_response):
    """WSGI application factory."""
    global __app__
    for key, value in environ.items():
        if key == 'SERVER_NAME':
            continue
        os.environ[key] = str(value)
        if __app__ is not None and key in __app__.config:
            __app__.config[key] = value
    if __app__ is None:
        __app__ = create_app()
    return __app__(environ, start_response)
