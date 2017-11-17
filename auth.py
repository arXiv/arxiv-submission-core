"""Toy authorizer implementation."""

import os
from flask import Flask, jsonify, request
import jwt
import logging

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
    if not auth_header:
        logger.info('Authorization header missing')
        return jsonify(NOPE), 403, {}
    try:
        auth_token = auth_header.split(" ")[1]
    except IndexError:
        logger.info('Authorization header malformed')
        return jsonify(NOPE), 403, {}

    logger.info('Got auth token %s', auth_token)
    claims = TOKENS.get(auth_token)
    if not claims:
        logger.info('Access token not valid')
        return jsonify(NOPE), 403, {}
    logger.info('Got claims: %s', str(claims))
    headers = {'Token': jwt.encode(claims, JWT_SECRET)}
    logger.info('Setting header: %s', str(headers))
    return jsonify({'status': 'OK!'}), 200, headers


def application(env, start_response):
    """WSGI application factory."""
    return app(env, start_response)
