from contextlib import contextmanager

from flask import Flask

from .. import init_app, create_all, drop_all, models, DBEvent, \
    get_submission, current_session, get_licenses, exceptions, store_event


@contextmanager
def in_memory_db(app=None):
    """Provide an in-memory sqlite database for testing purposes."""
    if app is None:
        app = Flask('foo')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    init_app(app)
    with app.app_context():

        create_all()
        try:
            yield current_session()
        except Exception:
            raise
        finally:
            drop_all()
