"""Utility classes and functions for :mod:`.classic`."""

import json
from contextlib import contextmanager
from typing import Optional, Generator

from sqlalchemy import create_engine
import sqlalchemy.types as types
from sqlalchemy.engine import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import sessionmaker

from arxiv.base.globals import get_application_config, get_application_global
from arxiv.base import logging
from .exceptions import ClassicBaseException, CommitFailed

logger = logging.getLogger(__name__)


class SQLiteJSON(types.TypeDecorator):
    """A SQLite-friendly JSON data type."""

    impl = types.TEXT

    def process_bind_param(self, value: Optional[dict], dialect: str) -> str:
        """Serialize a dict to JSON."""
        if value is not None:
            value = json.dumps(value)
        return value

    def process_result_value(self, value: str, dialect: str) -> Optional[dict]:
        """Deserialize JSON content to a dict."""
        if value is not None:
            value = json.loads(value)
        return value


# SQLite does not support JSON, so we extend JSON to use our custom data type
# as a variant for the 'sqlite' dialect.
FriendlyJSON = types.JSON().with_variant(SQLiteJSON, 'sqlite')


def get_engine(app: object = None) -> Engine:
    """Get a new :class:`.Engine` for the classic database."""
    config = get_application_config(app)
    database_uri = config.get('CLASSIC_DATABASE_URI', 'sqlite://')
    return create_engine(database_uri)


# TODO: consider making this private.
def get_session(app: object = None) -> Session:
    """Get a new :class:`.Session` for the classic database."""
    engine = current_engine()
    return sessionmaker(bind=engine)()


def current_engine() -> Engine:
    """Get/create :class:`.Engine` for this context."""
    g = get_application_global()
    if not g:
        return get_engine()
    if 'classic_engine' not in g:
        g.classic_engine = get_engine()    # type: ignore
    return g.classic_engine     # type: ignore


def current_session() -> Session:
    """Get/create :class:`.Session` for this context."""
    g = get_application_global()
    if not g:
        return get_session()
    if 'classic' not in g:
        g.classic = get_session()    # type: ignore
    return g.classic     # type: ignore


@contextmanager
def transaction() -> Generator:
    """Context manager for database transaction."""
    session = current_session()
    try:
        yield session
        session.commit()
    except ClassicBaseException as e:
        logger.debug('Commit failed, rolling back: %s', str(e))
        session.rollback()
        raise   # Propagate exceptions raised from this module.
    except Exception as e:
        logger.debug('Commit failed, rolling back: %s', str(e))
        session.rollback()
        raise CommitFailed('Failed to commit transaction') from e
