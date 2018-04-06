"""Toy authorizer implementation."""

import os
from flask import Flask, jsonify, request
import jwt
from arxiv.base import logging

logger = logging.getLogger(__name__)


JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')
TOKENS = {
    'as392lks0kk32': {
        'client': 'fooclient',
        'user': 'foouser',
        'scope': ['submission:write', 'submission:read']
    },
    'f0da9jso3l2m4': {
        'client': 'barclient',
        'user': 'baruser',
        'scope': ['submission:read']
    }
}
NOPE = {'reason': 'Missing or malformed authorization header'}

app = Flask('authorizer')


@app.route('/auth', methods=['GET'])
def authorize():
    """Authorize the request with an access token."""
    auth_header = request.headers.get('Authorization')
    logger.debug('Got auth header: %s', auth_header)
    if not auth_header:
        logger.debug('Authorization header missing')
        return jsonify(NOPE), 403, {}
    try:
        auth_token = auth_header.split(" ")[1]
    except IndexError:
        logger.debug('Authorization header malformed')
        return jsonify(NOPE), 403, {}

    logger.debug('Got auth token')
    claims = TOKENS.get(auth_token)
    if not claims:
        logger.debug('Access token not valid')
        return jsonify(NOPE), 403, {}
    logger.debug('Got claims: %s', str(claims))
    headers = {'Token': jwt.encode(claims, JWT_SECRET)}
    logger.debug('Setting header')
    return jsonify({'status': 'OK!'}), 200, headers


def application(env, start_response):
    """WSGI application factory."""
    return app(env, start_response)
