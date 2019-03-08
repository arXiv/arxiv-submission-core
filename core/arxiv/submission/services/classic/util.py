"""Utility classes and functions for :mod:`.services.classic`."""

import json
from contextlib import contextmanager
from typing import Optional, Generator

from flask import Flask
from sqlalchemy import create_engine
import sqlalchemy.types as types
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import sessionmaker
from flask_sqlalchemy import SQLAlchemy

from arxiv.base.globals import get_application_config, get_application_global
from arxiv.base import logging
from .exceptions import ClassicBaseException, TransactionFailed

from ... import serializer


class ClassicSQLAlchemy(SQLAlchemy):
    """SQLAlchemy integration for the classic database."""

    def init_app(self, app: Flask) -> None:
        """Set default configuration."""
        app.config.setdefault(
            'SQLALCHEMY_DATABASE_URI',
            app.config.get('CLASSIC_DATABASE_URI', 'sqlite://')
        )
        app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        super(ClassicSQLAlchemy, self).init_app(app)

    def apply_pool_defaults(self, app, options):
        """Set options for create_engine()."""
        super(ClassicSQLAlchemy, self).apply_pool_defaults(app, options)
        if app.config['SQLALCHEMY_DATABASE_URI'].startswith('mysql'):
            options['json_serializer'] = serializer.dumps
            options['json_deserializer'] = serializer.loads


db: SQLAlchemy = ClassicSQLAlchemy()


logger = logging.getLogger(__name__)


class SQLiteJSON(types.TypeDecorator):
    """A SQLite-friendly JSON data type."""

    impl = types.TEXT

    def process_bind_param(self, value: Optional[dict], dialect: str) -> str:
        """Serialize a dict to JSON."""
        if value is not None:
            value = serializer.dumps(value)
        return value

    def process_result_value(self, value: str, dialect: str) -> Optional[dict]:
        """Deserialize JSON content to a dict."""
        if value is not None:
            value = serializer.loads(value)
        return value


# SQLite does not support JSON, so we extend JSON to use our custom data type
# as a variant for the 'sqlite' dialect.
FriendlyJSON = types.JSON().with_variant(SQLiteJSON, 'sqlite')


def current_engine() -> Engine:
    """Get/create :class:`.Engine` for this context."""
    return db.engine


def current_session() -> Session:
    """Get/create :class:`.Session` for this context."""
    return db.session()


@contextmanager
def transaction() -> Generator:
    """Context manager for database transaction."""
    session = current_session()
    try:
        yield session
        session.commit()
    except ClassicBaseException as e:
        logger.debug('Command failed, rolling back: %s', str(e))
        session.rollback()
        raise   # Propagate exceptions raised from this module.
    except Exception as e:
        logger.debug('Command failed, rolling back: %s', str(e))
        session.rollback()
        raise TransactionFailed('Failed to execute transaction') from e
