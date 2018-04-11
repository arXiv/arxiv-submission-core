"""
Convience methods for request authorization.

For demonstration purposes only.
"""

import jwt
from flask import request, current_app, jsonify, g

DecodeError = jwt.exceptions.DecodeError


def get_auth_token() -> str:
    """Retrieve the Authorization header from the request."""
    return request.headers.get('Authorization')


def decode_authorization_token() -> dict:
    """Retrieve and decode a JWT from the Authorization header."""
    secret = current_app.config.get('JWT_SECRET')
    encoded = request.headers.get('Authorization')
    return jwt.decode(encoded, secret, algorithms=['HS256'])
