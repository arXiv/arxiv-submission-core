from typing import Optional
import os
import uuid
from datetime import datetime, timedelta

from pytz import timezone

from arxiv.users import auth, domain


DEFAULT_SCOPES = " ".join(([
    "public:read",
    "submission:create",
    "submission:update",
    "submission:read",
    "upload:create",
    "upload:update",
    "upload:read",
    "upload:delete",
    "upload:read_logs"
]))

DEFAULT_SECRET = os.environ.get('JWT_SECRET', 'foosecret')


def generate_client_token(client_id: str, owner_id: str, name: str,
                          url: Optional[str] = None,
                          description: Optional[str] = None,
                          redirect_uri: Optional[str] = None,
                          scope: str = DEFAULT_SCOPES,
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
        scopes=[domain.Scope(*s.split(':')) for s in scope.split()],
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
