"""Provides scope-based authorization with JWT."""

from functools import wraps
from flask import request, current_app, jsonify
import jwt

from submit import status


INVALID_TOKEN = {'reason': 'Invalid authorization token'}
INVALID_SCOPE = {'reason': 'Token not authorized for this action'}


def scoped(scope: str):
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
            except jwt.exceptions.DecodeError:
                return jsonify(INVALID_TOKEN), status.HTTP_403_FORBIDDEN, {}
            if scope not in decoded.get('scope'):
                return jsonify(INVALID_SCOPE), status.HTTP_403_FORBIDDEN, {}
            return func(*args, **kwargs)
        return wrapper
    return protector
