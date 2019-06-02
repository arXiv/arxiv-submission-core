from typing import Any, Dict, Callable, Mapping, List
import logging
import time

from flask import Flask, Config
from collections import defaultdict

from arxiv import mail, vault
from arxiv.base import Base, logging
from arxiv.base.middleware import wrap, request_logs
from arxiv.submission import init_app, wait_for
from arxiv.submission.services import Classifier, PlainTextService, Compiler, \
    classic
from . import config
from .services import database

logger = logging.getLogger(__name__)

Callback = Callable[['ConfigWithHooks', str, Any], None]


class ConfigWithHooks(Config):
    """Config object that has __setitem__ hooks."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Make a place for hooks on init."""
        super(ConfigWithHooks, self).__init__(*args, **kwargs)
        self._hooks: Mapping[str, List[Callback]] = defaultdict(list)

    def add_hook(self, key: str, hook: Callback) -> None:
        """
        Add a callback/hook for a config key.

        The hook will be called when the ``key`` is set.
        """
        self._hooks[key].append(hook)

    def __setitem__(self, key: str, value: Any) -> None:
        """Set a config ``key``, and call registered hooks."""
        super(ConfigWithHooks, self).__setitem__(key, value)
        for hook in self._hooks.get(key, []):
            hook(self, key, value)


Flask.config_class = ConfigWithHooks    # type: ignore


def update_binds(config: ConfigWithHooks, key: str, value: Any) -> None:
    """Update :const:`.config.SQLALCHEMY_BINDS.`."""
    config['SQLALCHEMY_BINDS'] = {
        'agent': config['SUBMISSION_AGENT_DATABASE_URI']
    }


def create_app() -> Flask:
    """Create a new agent application."""
    app = Flask(__name__)
    app.config.from_object(config)
    app.config.add_hook('SUBMISSION_AGENT_DATABASE_URI', update_binds)

    Base(app)

    # Register logging and secrets middleware.
    middleware = [request_logs.ClassicLogsMiddleware]
    if app.config['VAULT_ENABLED']:
        middleware.insert(0, vault.middleware.VaultMiddleware)
    wrap(app, middleware)

    # Make sure that we have all of the secrets that we need to run.
    if app.config['VAULT_ENABLED']:
        app.middlewares['VaultMiddleware'].update_secrets({})

    logger.info(app.config)

    # Initialize services.
    database.init_app(app)
    with app.app_context():
        if not database.tables_exist():
            database.create_all()
    mail.init_app(app)
    Classifier.init_app(app)
    Compiler.init_app(app)
    PlainTextService.init_app(app)
    init_app(app)

    if app.config['WAIT_FOR_SERVICES']:
        time.sleep(app.config['WAIT_ON_STARTUP'])
        with app.app_context():
            wait_for(database)
            wait_for(Classifier.current_session(),
                     timeout=app.config['CLASSIFIER_STATUS_TIMEOUT'])
            wait_for(Compiler.current_session(),
                     timeout=app.config['COMPILER_STATUS_TIMEOUT'])
            wait_for(PlainTextService.current_session(),
                     timeout=app.config['PLAINTEXT_STATUS_TIMEOUT'])
            # FILE_MANAGER_STATUS_TIMEOUT
        logger.info('All upstream services are available; ready to start')
    return app
