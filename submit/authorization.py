"""Provides scope-based authorization with JWT."""

from functools import wraps
from flask import request, current_app, jsonify, g
import jwt

from submit import status


INVALID_TOKEN = {'reason': 'Invalid authorization token'}
INVALID_SCOPE = {'reason': 'Token not authorized for this action'}

READ = 'submission:read'
WRITE = 'submission:write'
MODERATE = 'submission:moderate'


def scoped(scope_required: str):
    """Generate a decorator to enforce scope authorization."""
    def protector(func):
        """Decorator that provides scope enforcement."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            """Check the authorization token before executing the method."""
            secret = current_app.config.get('JWT_SECRET')
            encoded = request.headers.get('Authorization')
            try:
                decoded = jwt.decode(encoded, secret, algorithms=['HS256'])
                scope = decoded.get('scope')
            except jwt.exceptions.DecodeError:
                return jsonify(INVALID_TOKEN), status.HTTP_403_FORBIDDEN, {}
            if scope_required not in scope:
                return jsonify(INVALID_SCOPE), status.HTTP_403_FORBIDDEN, {}
            g.user = decoded.get('user')
            g.client = decoded.get('client')
            g.scope = scope
            return func(*args, **kwargs)
        return wrapper
    return protector
