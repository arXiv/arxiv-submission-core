from typing import Optional
import os
import uuid
from datetime import datetime, timedelta

from pytz import timezone

from arxiv.users import auth, domain


DEFAULT_SCOPE = ','.join([
    auth.scopes.CREATE_SUBMISSION,
    auth.scopes.EDIT_SUBMISSION,
    auth.scopes.VIEW_SUBMISSION,
    auth.scopes.WRITE_UPLOAD,
    auth.scopes.READ_UPLOAD
])

DEFAULT_SECRET = os.environ.get('JWT_SECRET', 'foosecret')


def generate_client_token(client_id: str, owner_id: str, name: str,
                          url: Optional[str] = None,
                          description: Optional[str] = None,
                          redirect_uri: Optional[str] = None,
                          scope: str = DEFAULT_SCOPE,
                          expires: int = 36000,
                          endorsements: str = 'astro-ph.CO,astro-ph.GA',
                          secret: str = DEFAULT_SECRET) -> None:
    # Specify the validity period for the session.
    start = datetime.now(tz=timezone('US/Eastern'))
    end = start + timedelta(seconds=expires)

    client = domain.Client(
        client_id=client_id,
        owner_id=owner_id,
        name=name,
        url=url,
        description=description,
        redirect_uri=redirect_uri
    )
    authorizations = domain.Authorizations(
        scopes=scope.split(','),
        endorsements=[domain.Category(*cat.split('.', 1))
                      for cat in endorsements.split(',')]
    )
    session = domain.Session(
        session_id=str(uuid.uuid4()),
        start_time=start, end_time=end,
        client=client,
        authorizations=authorizations
    )
    return auth.tokens.encode(session, secret)


def generate_user_token(user_id: str, email: str, username: str,
                        first_name: str = 'Jane', last_name: str = 'Doe',
                        suffix_name: str = 'IV',
                        affiliation: str = 'Cornell University',
                        rank: int = 3,
                        country: str = 'us',
                        default_category: str = 'astro-ph.GA',
                        submission_groups: str = 'grp_physics',
                        endorsements: str = 'astro-ph.CO,astro-ph.GA',
                        scope: str = DEFAULT_SCOPE,
                        secret: str = DEFAULT_SECRET):
    # Specify the validity period for the session.
    start = datetime.now(tz=timezone('US/Eastern'))
    end = start + timedelta(seconds=36000)   # Make this as long as you want.

    # Create a user with endorsements in astro-ph.CO and .GA.
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
                default_category=domain.Category(
                    *default_category.split('.', 1)
                ),
                submission_groups=submission_groups.split(',')
            )
        ),
        authorizations=domain.Authorizations(
            scopes=[scope.split(',')],
            endorsements=[domain.Category(*cat.split('.', 1))
                          for cat in endorsements.split(',')]
        )
    )
    return auth.tokens.encode(session, secret)
