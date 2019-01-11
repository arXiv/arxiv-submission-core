"""Initialize the worker application."""

from flask import Flask
from .rules import get_or_create_worker_app
from . import init_app

app = Flask(__name__)
app.app_context().push()
init_app(app)
worker_app = get_or_create_worker_app()
