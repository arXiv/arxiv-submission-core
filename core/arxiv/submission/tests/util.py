from contextlib import contextmanager

from flask import Flask

from ..services import classic


@contextmanager
def in_memory_db():
    """Provide an in-memory sqlite database for testing purposes."""
    app = Flask('foo')
    app.config['CLASSIC_DATABASE_URI'] = 'sqlite://'

    with app.app_context():
        classic.init_app(app)
        classic.create_all()
        try:
            yield classic.current_session()
        except Exception:
            raise
        finally:
            classic.drop_all()
