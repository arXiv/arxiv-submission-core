from typing import Optional
from contextlib import contextmanager

from flask import Flask

from ..services import classic


@contextmanager
def in_memory_db(app: Optional[Flask] = None):
    """Provide an in-memory sqlite database for testing purposes."""
    if app is None:
        app = Flask('foo')
    app.config['CLASSIC_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        classic.init_app(app)
        classic.create_all()
        try:
            yield classic.current_session()
        except Exception:
            raise
        finally:
            classic.drop_all()
