import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List

from flask import Flask
from pytz import UTC

from arxiv.users import domain, auth

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


# Generate authentication token
def generate_token(app: Flask, scope: List[str]) -> str:
    """Helper function for generating a JWT."""
    secret = app.config.get('JWT_SECRET')
    start = datetime.now(tz=UTC)
    end = start + timedelta(seconds=36000)  # Make this as long as you want.
    user_id = '1'
    email = 'foo@bar.com'
    username = 'theuser'
    first_name = 'Jane'
    last_name = 'Doe'
    suffix_name = 'IV'
    affiliation = 'Cornell University'
    rank = 3
    country = 'us'
    default_category = 'astro-ph.GA'
    submission_groups = 'grp_physics'
    endorsements = 'astro-ph.CO,astro-ph.GA'
    session = domain.Session(
        session_id=str(uuid.uuid4()),
        start_time=start, end_time=end,
        user=domain.User(
            user_id=user_id,
            email=email,
            username=username,
            name=domain.UserFullName(first_name, last_name, suffix_name),
            profile=domain.UserProfile(
                affiliation=affiliation,
                rank=int(rank),
                country=country,
                default_category=domain.Category(default_category),
                submission_groups=submission_groups.split(',')
            )
        ),
        authorizations=domain.Authorizations(
            scopes=scope,
            endorsements=[domain.Category(cat.split('.', 1))
                          for cat in endorsements.split(',')]
        )
    )
    token = auth.tokens.encode(session, secret)
    return token