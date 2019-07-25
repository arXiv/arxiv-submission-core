
from typing import List
import uuid
from datetime import datetime, timedelta
from pytz import UTC

from arxiv.users import auth, domain
from arxiv.base.globals import get_application_config

from .domain.agent import User, Agent, Client


def get_system_token(name: str, agent: Agent, scopes: List[str]) -> str:
    start = datetime.now(tz=UTC)
    end = start + timedelta(seconds=36000)
    if isinstance(agent, User):
        user = domain.User(
            username=agent.username,
            email=agent.email,
            user_id=agent.identifier,
            name=agent.name,
            verified=True
        )
    else:
        user = None
    session = domain.Session(
        session_id=str(uuid.uuid4()),
        start_time=datetime.now(), end_time=end,
        user=user,
        client=domain.Client(
            owner_id='system',
            client_id=name,
            name=name
        ),
        authorizations=domain.Authorizations(scopes=scopes)
    )
    return auth.tokens.encode(session, get_application_config()['JWT_SECRET'])


def get_compiler_scopes(resource: str) -> List[str]:
    """Get minimal auth scopes necessary for compilation integration."""
    return [auth.scopes.READ_COMPILE.for_resource(resource),
            auth.scopes.CREATE_COMPILE.for_resource(resource)]
