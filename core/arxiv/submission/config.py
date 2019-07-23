"""Submission core configuration parameters."""

from os import environ
import warnings
from kombu.serialization import register
from .serializer import dumps, loads

NAMESPACE = environ.get('NAMESPACE')
"""Namespace in which this service is deployed; to qualify keys for secrets."""

LOGLEVEL = int(environ.get('LOGLEVEL', '20'))
"""
Logging verbosity.

See `https://docs.python.org/3/library/logging.html#levels`_.
"""

JWT_SECRET = environ.get('JWT_SECRET')
"""Secret key for signing + verifying authentication JWTs."""

if not JWT_SECRET:
    warnings.warn('JWT_SECRET is not set; authn/z may not work correctly!')

CORE_VERSION = "0.0.0"

MAX_SAVE_RETRIES = 25
"""Number of times to retry storing/emiting a submission event."""

DEFAULT_SAVE_RETRY_DELAY = 30
"""Delay between retry attempts when storing/emiting a submission event."""

WAIT_FOR_SERVICES = bool(int(environ.get('WAIT_FOR_SERVICES', '0')))
"""Disable/enable waiting for upstream services to be available on startup."""
if not WAIT_FOR_SERVICES:
    warnings.warn('Awaiting upstream services is disabled; this should'
                  ' probably be enabled in production.')

WAIT_ON_STARTUP = int(environ.get('WAIT_ON_STARTUP', '0'))
"""Number of seconds to wait before checking upstream services on startup."""

ENABLE_CALLBACKS = bool(int(environ.get('ENABLE_CALLBACKS', '1')))
"""Enable/disable the :func:`Event.bind` feature."""


# --- DATABASE CONFIGURATION ---

CLASSIC_DATABASE_URI = environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')
"""Full database URI for the classic system."""

SQLALCHEMY_DATABASE_URI = CLASSIC_DATABASE_URI
"""Full database URI for the classic system."""

SQLALCHEMY_TRACK_MODIFICATIONS = False
"""Track modifications feature should always be disabled."""

# --- AWS CONFIGURATION ---

AWS_ACCESS_KEY_ID = environ.get('AWS_ACCESS_KEY_ID', 'nope')
"""
Access key for requests to AWS services.

If :const:`VAULT_ENABLED` is ``True``, this will be overwritten.
"""

AWS_SECRET_ACCESS_KEY = environ.get('AWS_SECRET_ACCESS_KEY', 'nope')
"""
Secret auth key for requests to AWS services.

If :const:`VAULT_ENABLED` is ``True``, this will be overwritten.
"""

AWS_REGION = environ.get('AWS_REGION', 'us-east-1')
"""Default region for calling AWS services."""


# --- KINESIS CONFIGURATION ---

KINESIS_STREAM = environ.get("KINESIS_STREAM", "SubmissionEvents")
"""Name of the stream on which to produce and consume events."""

KINESIS_SHARD_ID = environ.get("KINESIS_SHARD_ID", "0")
"""Shard ID for stream producer."""

KINESIS_ENDPOINT = environ.get("KINESIS_ENDPOINT", None)
"""
Alternate endpoint for connecting to Kinesis.

If ``None``, uses the boto3 defaults for the :const:`AWS_REGION`. This is here
mainly to support development with localstack or other mocking frameworks.
"""

KINESIS_VERIFY = bool(int(environ.get("KINESIS_VERIFY", "1")))
"""
Enable/disable TLS certificate verification when connecting to Kinesis.

This is here support development with localstack or other mocking frameworks.
"""

if not KINESIS_VERIFY:
    warnings.warn('Certificate verification for Kinesis is disabled; this'
                  ' should not be disabled in production.')

# --- UPSTREAM SERVICE INTEGRATIONS ---
#
# See https://kubernetes.io/docs/concepts/services-networking/service/#environment-variables
# for details on service DNS and environment variables in k8s.

# Integration with the file manager service.
FILEMANAGER_HOST = environ.get('FILEMANAGER_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the filemanager service."""

FILEMANAGER_PORT = environ.get('FILEMANAGER_SERVICE_PORT', '443')
"""Port for the filemanager service."""

FILEMANAGER_PROTO = environ.get(f'FILEMANAGER_PORT_{FILEMANAGER_PORT}_PROTO',
                                 'https')
"""Protocol for the filemanager service."""

FILEMANAGER_PATH = environ.get('FILEMANAGER_PATH', '').lstrip('/')
"""Path at which the filemanager service is deployed."""

FILEMANAGER_ENDPOINT = environ.get(
    'FILEMANAGER_ENDPOINT',
    '%s://%s:%s/%s' % (FILEMANAGER_PROTO, FILEMANAGER_HOST,
                       FILEMANAGER_PORT, FILEMANAGER_PATH)
)
"""
Full URL to the root filemanager service API endpoint.

If not explicitly provided, this is composed from :const:`FILEMANAGER_HOST`,
:const:`FILEMANAGER_PORT`, :const:`FILEMANAGER_PROTO`, and
:const:`FILEMANAGER_PATH`.
"""

FILEMANAGER_VERIFY = bool(int(environ.get('FILEMANAGER_VERIFY', '1')))
"""Enable/disable SSL certificate verification for filemanager service."""

if FILEMANAGER_PROTO == 'https' and not FILEMANAGER_VERIFY:
    warnings.warn('Certificate verification for filemanager is disabled; this'
                  ' should not be disabled in production.')

# Integration with the compiler service.
COMPILER_HOST = environ.get('COMPILER_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the compiler service."""

COMPILER_PORT = environ.get('COMPILER_SERVICE_PORT', '443')
"""Port for the compiler service."""

COMPILER_PROTO = environ.get(f'COMPILER_PORT_{COMPILER_PORT}_PROTO', 'https')
"""Protocol for the compiler service."""

COMPILER_PATH = environ.get('COMPILER_PATH', '')
"""Path at which the compiler service is deployed."""

COMPILER_ENDPOINT = environ.get(
    'COMPILER_ENDPOINT',
    '%s://%s:%s/%s' % (COMPILER_PROTO, COMPILER_HOST, COMPILER_PORT,
                       COMPILER_PATH)
)
"""
Full URL to the root compiler service API endpoint.

If not explicitly provided, this is composed from :const:`COMPILER_HOST`,
:const:`COMPILER_PORT`, :const:`COMPILER_PROTO`, and :const:`COMPILER_PATH`.
"""

COMPILER_VERIFY = bool(int(environ.get('COMPILER_VERIFY', '1')))
"""Enable/disable SSL certificate verification for compiler service."""

if COMPILER_PROTO == 'https' and not COMPILER_VERIFY:
    warnings.warn('Certificate verification for compiler is disabled; this'
                  ' should not be disabled in production.')

# Integration with the classifier service.
CLASSIFIER_HOST = environ.get('CLASSIFIER_SERVICE_HOST', 'localhost')
"""Hostname or addreess of the classifier service."""

CLASSIFIER_PORT = environ.get('CLASSIFIER_SERVICE_PORT', '8000')
"""Port for the classifier service."""

CLASSIFIER_PROTO = environ.get(f'CLASSIFIER_PORT_{CLASSIFIER_PORT}_PROTO',
                               'http')
"""Protocol for the classifier service."""

CLASSIFIER_PATH = environ.get('CLASSIFIER_PATH', '/classifier/')
"""Path at which the classifier service is deployed."""

CLASSIFIER_ENDPOINT = environ.get(
    'CLASSIFIER_ENDPOINT',
    '%s://%s:%s/%s' % (CLASSIFIER_PROTO, CLASSIFIER_HOST, CLASSIFIER_PORT,
                       CLASSIFIER_PATH)
)
"""
Full URL to the root classifier service API endpoint.

If not explicitly provided, this is composed from :const:`CLASSIFIER_HOST`,
:const:`CLASSIFIER_PORT`, :const:`CLASSIFIER_PROTO`, and
:const:`CLASSIFIER_PATH`.
"""

CLASSIFIER_VERIFY = bool(int(environ.get('CLASSIFIER_VERIFY', '0')))
"""Enable/disable SSL certificate verification for classifier service."""

if CLASSIFIER_PROTO == 'https' and not CLASSIFIER_VERIFY:
    warnings.warn('Certificate verification for classifier is disabled; this'
                  ' should not be disabled in production.')

# Integration with plaintext extraction service.
PLAINTEXT_HOST = environ.get('PLAINTEXT_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the plaintext extraction service."""

PLAINTEXT_PORT = environ.get('PLAINTEXT_SERVICE_PORT', '443')
"""Port for the plaintext extraction service."""

PLAINTEXT_PROTO = environ.get(f'PLAINTEXT_PORT_{PLAINTEXT_PORT}_PROTO',
                              'https')
"""Protocol for the plaintext extraction service."""

PLAINTEXT_PATH = environ.get('PLAINTEXT_PATH', '')
"""Path at which the plaintext extraction service is deployed."""

PLAINTEXT_ENDPOINT = environ.get(
    'PLAINTEXT_ENDPOINT',
    '%s://%s:%s/%s' % (PLAINTEXT_PROTO, PLAINTEXT_HOST, PLAINTEXT_PORT,
                       PLAINTEXT_PATH)
)
"""
Full URL to the root plaintext extraction service API endpoint.

If not explicitly provided, this is composed from :const:`PLAINTEXT_HOST`,
:const:`PLAINTEXT_PORT`, :const:`PLAINTEXT_PROTO`, and :const:`PLAINTEXT_PATH`.
"""

PLAINTEXT_VERIFY = bool(int(environ.get('PLAINTEXT_VERIFY', '1')))
"""Enable/disable certificate verification for plaintext extraction service."""

if PLAINTEXT_PROTO == 'https' and not PLAINTEXT_VERIFY:
    warnings.warn('Certificate verification for plaintext extraction service'
                  ' is disabled; this should not be disabled in production.')

# Email notification configuration.
EMAIL_ENABLED = bool(int(environ.get('EMAIL_ENABLED', '1')))
"""Enable/disable sending e-mail. Default is enabled (True)."""

DEFAULT_SENDER = environ.get('DEFAULT_SENDER', 'noreply@arxiv.org')
"""Default sender address for e-mail."""

SUPPORT_EMAIL = environ.get('SUPPORT_EMAIL', "help@arxiv.org")
"""E-mail address for user support."""

SMTP_HOSTNAME = environ.get('SMTP_HOSTNAME', 'localhost')
"""Hostname for the SMTP server."""

SMTP_USERNAME = environ.get('SMTP_USERNAME', 'foouser')
"""Username for the SMTP server."""

SMTP_PASSWORD = environ.get('SMTP_PASSWORD', 'foopass')
"""Password for the SMTP server."""

SMTP_PORT = int(environ.get('SMTP_PORT', '0'))
"""SMTP service port."""

SMTP_LOCAL_HOSTNAME = environ.get('SMTP_LOCAL_HOSTNAME', None)
"""Local host name to include in SMTP request."""

SMTP_SSL = bool(int(environ.get('SMTP_SSL', '0')))
"""Enable/disable SSL for SMTP. Default is disabled."""

if not SMTP_SSL:
    warnings.warn('Certificate verification for SMTP is disabled; this'
                  ' should not be disabled in production.')


# --- URL GENERATION ---

EXTERNAL_URL_SCHEME = environ.get('EXTERNAL_URL_SCHEME', 'https')
"""Scheme to use for external URLs."""

if EXTERNAL_URL_SCHEME != 'https':
    warnings.warn('External URLs will not use HTTPS proto')

BASE_SERVER = environ.get('BASE_SERVER', 'arxiv.org')
"""Base arXiv server."""

SERVER_NAME = environ.get('SERVER_NAME', "submit.arxiv.org")
"""The name of this server."""

URLS = [
    ("submission", "/<int:submission_id>", SERVER_NAME),
    ("confirmation", "/<int:submission_id>/confirmation", SERVER_NAME)
]
"""
URLs for external services, for use with :func:`flask.url_for`.

This subset of URLs is common only within submit, for now - maybe move to base
if these pages seem relevant to other services.

For details, see :mod:`arxiv.base.urls`.
"""
