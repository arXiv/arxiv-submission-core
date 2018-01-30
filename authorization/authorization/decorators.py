"""Provides scope-based authorization with JWT."""

from functools import wraps
from flask import g
from arxiv import status
from . import decode_authorization_token, DecodeError, get_auth_token


INVALID_TOKEN = {'reason': 'Invalid authorization token'}
INVALID_SCOPE = {'reason': 'Token not authorized for this action'}


def scoped(scope_required: str):
    """Generate a decorator to enforce scope authorization."""
    def protector(func):
        """Decorator that provides scope enforcement."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Check the authorization token before executing the method."""
            # Attach the encrypted token so that we can use it in subrequests.
            g.token = get_auth_token()

            try:
                decoded = decode_authorization_token()
                scope = decoded.get('scope')
            except DecodeError:
                return INVALID_TOKEN, status.HTTP_403_FORBIDDEN, {}
            if scope_required not in scope:
                return INVALID_SCOPE, status.HTTP_403_FORBIDDEN, {}
            g.user = decoded.get('user')
            g.client = decoded.get('client')
            g.scope = scope

            return func(*args, **kwargs)
        return wrapper
    return protector
