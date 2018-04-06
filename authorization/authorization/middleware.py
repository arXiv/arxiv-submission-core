"""Middleware for decoding encrypted JWTs on each request."""

import os
from typing import Callable, Iterable, Tuple
import jwt

from arxiv.base.middleware import BaseMiddleware


class AuthMiddleware(BaseMiddleware):
    """
    Middleware to handle auth information on requests.

    Before the request is handled by the application, the ``Authorization``
    header is parsed for an encrypted JWT. If successfully decrypted,
    information about the user and their authorization scope is attached
    to the request.

    This can be accessed in the application via
    ``flask.request.environ['auth']``.  If Authorization header was not
    included, or if the JWT could not be decrypted, then that value will be
    ``None``.
    """

    def before(self, environ: dict, start_response: Callable) \
            -> Tuple[dict, Callable]:
        """Parse the ``Authorization`` header in the response."""
        token = environ.get('HTTP_AUTHORIZATION')
        jwt_secret = os.environ.get('JWT_SECRET')
        environ['auth'] = None
        if not token:
            return environ, start_response
        try:
            decoded = jwt.decode(token, jwt_secret, algorithms=['HS256'])
        except jwt.exceptions.DecodeError:  # type: ignore
            return environ, start_response

        environ['auth'] = {
            'scope': decoded.get('scope', []),
            'user': decoded.get('user'),
            'client': decoded.get('client'),
            'token': token
        }
        return environ, start_response
