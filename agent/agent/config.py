"""Submission agent configuration parameters."""

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
"""Version of the :mod:`arxiv.submission` package."""

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


# --- VAULT INTEGRATION CONFIGURATION ---

VAULT_ENABLED = bool(int(environ.get('VAULT_ENABLED', '0')))
"""Enable/disable secret retrieval from Vault."""

if not VAULT_ENABLED:
    warnings.warn('Vault integration is disabled')

KUBE_TOKEN = environ.get('KUBE_TOKEN', 'fookubetoken')
"""Service account token for authenticating with Vault. May be a file path."""

VAULT_HOST = environ.get('VAULT_HOST', 'foovaulthost')
"""Vault hostname/address."""

VAULT_PORT = environ.get('VAULT_PORT', '1234')
"""Vault API port."""

VAULT_ROLE = environ.get('VAULT_ROLE', 'submission-agent')
"""Vault role linked to this application's service account."""

VAULT_CERT = environ.get('VAULT_CERT')
"""Path to CA certificate for TLS verification when talking to Vault."""

VAULT_SCHEME = environ.get('VAULT_SCHEME', 'https')
"""Default is ``https``."""

if VAULT_ENABLED and VAULT_SCHEME != 'https':
    warnings.warn('Vault is not configured to use TLS; this is not safe for'
                  ' production!')

NS_AFFIX = '' if NAMESPACE == 'production' else f'-{NAMESPACE}'
VAULT_REQUESTS = [
    {'type': 'generic',
     'name': 'JWT_SECRET',
     'mount_point': f'secret{NS_AFFIX}/',
     'path': 'jwt',
     'key': 'jwt-secret',
     'minimum_ttl': 3600},
    {'type': 'generic',
     'name': 'SQLALCHEMY_DATABASE_URI',
     'mount_point': f'secret{NS_AFFIX}/',
     'path': 'beta-mysql',
     'key': 'uri',
     'minimum_ttl': 360000},
    {'type': 'aws',
     'name': 'AWS_S3_CREDENTIAL',
     'mount_point': f'aws{NS_AFFIX}/',
     'role': environ.get('VAULT_CREDENTIAL')},
    {'type': 'database',
     'engine': environ.get('AGENT_DATABASE_ENGINE', 'mysql+mysqldb'),
     'host': environ.get('AGENT_DATABASE_HOST', 'localhost'),
     'database': environ.get('AGENT_DATABASE_NAME', 'agent'),
     'params': 'charset=utf8mb4',
     'port': environ.get('AGENT_DATABASE_PORT', '3306'),
     'name': 'SUBMISSION_AGENT_DATABASE_URI',
     'mount_point': f'database{NS_AFFIX}/',
     'role': 'submission-agent-write'}
]
"""Requests for Vault secrets."""


# --- DATABASE CONFIGURATION ---

CLASSIC_DATABASE_URI = environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')
"""Full database URI for the classic system."""

SQLALCHEMY_DATABASE_URI = CLASSIC_DATABASE_URI
"""Full database URI for the classic system."""

SQLALCHEMY_TRACK_MODIFICATIONS = False
"""Track modifications feature should always be disabled."""

SUBMISSION_AGENT_DATABASE_URI = environ.get('SUBMISSION_AGENT_DATABASE_URI',
                                            'sqlite:///')
"""Full database URI for the agent checkpoint database."""

SQLALCHEMY_BINDS = {'agent': SUBMISSION_AGENT_DATABASE_URI}
"""
Binding for the agent checkpoint database.

See `https://flask-sqlalchemy.palletsprojects.com/en/2.x/binds/`_.
"""

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
"""
Shard ID for this agent instance.

There must only be one agent process running per shard.
"""

KINESIS_START_TYPE = environ.get("KINESIS_START_TYPE", "TRIM_HORIZON")
"""Start type to use when no checkpoint is available."""

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


# --- CELERY CONFIGURATION ---

BROKER_URL = environ.get('SUBMISSION_AGENT_BROKER_URL',
                         'redis://localhost:6379/0')
"""The full URL for the task broker."""

RESULT_BACKEND = environ.get('SUBMISSION_AGENT_RESULT_BACKEND', BROKER_URL)
"""
The full URL for the result backend.

Currently we use the same backend for both queuing and storing results.
"""

QUEUE_NAME_PREFIX = environ.get('SUBMISSION_AGENT_QUEUE_NAME_PREFIX',
                                'submission-agent-')
"""Used to differentiate our tasks from those of others on a shared broker."""

TASK_DEFAULT_QUEUE = 'submission-worker'

PREFETCH_MULTIPLIER = int(environ.get(
    'SUBMISSION_AGENT_WORKER_PREFETCH_MULTIPLIER',
    '1'
))
"""Number of tasks to be fetched at once by each worker."""

TASK_ACKS_LATE = bool(int(environ.get('SUBMISSION_AGENT_TASK_ACKS_LATE', '1')))
"""If True (default), tasks are acknowledged after they are completed."""

# Configure Celery to use our custom JSON serializer.
register('process-json', dumps, loads,
         content_type='application/x-process-json',
         content_encoding='utf-8')
CELERY_ACCEPT_CONTENT = ['process-json']
"""Serialization formats supported by Celery."""

CELERY_TASK_SERIALIZER = 'process-json'
"""Serializer for Celery tasks."""

CELERY_RESULT_SERIALIZER = 'process-json'
"""Serialize for celery results."""


# --- UPSTREAM SERVICE INTEGRATIONS ---
#
# See https://kubernetes.io/docs/concepts/services-networking/service/#environment-variables
# for details on service DNS and environment variables in k8s.

# Integration with the file manager service.
FILEMANAGER_HOST = environ.get('FILEMANAGER_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the filemanager service."""

FILEMANAGER_PORT = environ.get('FILEMANAGER_SERVICE_PORT', '443')
"""Port for the filemanager service."""

FILEMANAGER_PROTO = environ.get(
    f'FILEMANAGER_PORT_{FILEMANAGER_PORT}_PROTO',
    environ.get('FILEMANAGER_PROTO', 'https')
)
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

FILEMANAGER_STATUS_TIMEOUT \
    = float(environ.get('FILEMANAGER_STATUS_TIMEOUT', 1.0))

if FILEMANAGER_PROTO == 'https' and not FILEMANAGER_VERIFY:
    warnings.warn('Certificate verification for filemanager is disabled; this'
                  ' should not be disabled in production.')

# Integration with the compiler service.
COMPILER_HOST = environ.get('COMPILER_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the compiler service."""

COMPILER_PORT = environ.get('COMPILER_SERVICE_PORT', '443')
"""Port for the compiler service."""

COMPILER_PROTO = environ.get(
    f'COMPILER_PORT_{COMPILER_PORT}_PROTO',
    environ.get('COMPILER_PROTO', 'https')
)
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

COMPILER_STATUS_TIMEOUT \
    = float(environ.get('COMPILER_STATUS_TIMEOUT', 1.0))

if COMPILER_PROTO == 'https' and not COMPILER_VERIFY:
    warnings.warn('Certificate verification for compiler is disabled; this'
                  ' should not be disabled in production.')

# Integration with the classifier service.
CLASSIFIER_HOST = environ.get('CLASSIFIER_SERVICE_HOST', 'localhost')
"""Hostname or addreess of the classifier service."""

CLASSIFIER_PORT = environ.get('CLASSIFIER_SERVICE_PORT', '8000')
"""Port for the classifier service."""

CLASSIFIER_PROTO = environ.get(
    f'CLASSIFIER_PORT_{CLASSIFIER_PORT}_PROTO',
    environ.get('CLASSIFIER_PROTO', 'http')
)
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

CLASSIFIER_STATUS_TIMEOUT \
    = float(environ.get('CLASSIFIER_STATUS_TIMEOUT', 1.0))

if CLASSIFIER_PROTO == 'https' and not CLASSIFIER_VERIFY:
    warnings.warn('Certificate verification for classifier is disabled; this'
                  ' should not be disabled in production.')

# Integration with plaintext extraction service.
PLAINTEXT_HOST = environ.get('PLAINTEXT_SERVICE_HOST', 'arxiv.org')
"""Hostname or addreess of the plaintext extraction service."""

PLAINTEXT_PORT = environ.get('PLAINTEXT_SERVICE_PORT', '443')
"""Port for the plaintext extraction service."""

PLAINTEXT_PROTO = environ.get(
    f'PLAINTEXT_PORT_{PLAINTEXT_PORT}_PROTO',
    environ.get('PLAINTEXT_PROTO', 'https')
)
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

PLAINTEXT_STATUS_TIMEOUT \
    = float(environ.get('PLAINTEXT_STATUS_TIMEOUT', 1.0))

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


# --- CONFIGURATION FOR SUBMISSION POLICIES ---
#
# The following parameters were carried forward from the legacy system. In
# future versions, these should be stored in a configuration database that can
# be directly altered via administrative interfaces.
#
# Not all of these parameters may be directly used right now.

# TODO: make this configurable
RECLASSIFY_PROPOSAL_THRESHOLD = 0.57   # Equiv. to logodds of 0.3.
"""This is the threshold for generating a proposal from a classifier result."""

# TODO: make this configurable.
LOW_STOP_PERCENT = 0.10
"""This is the threshold for abornmally low stopword content by percentage."""

LOW_STOP = 400
"""This is the threshold for abornmally low stopword content by count."""

HIGH_STOP_PERCENT = 0.30
"""This is the threshold for abnormally high stopword content by percentage."""

MULTIPLE_LIMIT = 1.01
"""Threshold for repeated text."""

LINENOS_LIMIT = 0
"""Threshold for line numbers."""

TITLE_SIMILARITY_WINDOW = 3*365/12    # days
"""Number of days in the past to look for similar titles."""

TITLE_SIMILARITY_THRESHOLD = 0.7
"""Jaccard similarity threshold for title similarity."""

METADATA_ASCII_THRESHOLD = 0.5
"""Minimum ASCII content for titles and abstracts (0.-1.)."""

COMPRESSED_PACKAGE_MAX_BYTES = 6_000_000
"""Maximum size of a source package in bytes when compressed."""

UNCOMPRESSED_PACKAGE_MAX_BYTES = 18_000_000
"""Maximum size of a source package in bytes when uncompressed."""

PDF_LIMIT_BYTES = 15_000_000
"""The maximum size in bytes of the provided/compiled PDF."""

NO_RECLASSIFY_CATEGORIES = (
    'cs.CE',   # Interdisciplinary category (see ARXIVOPS-466).
)
"""
Don't make auto-proposals for these user-supplied primary categories.

These categories may not be known to the classifier, or the
classifier-suggested alternatives may be consistently innaccurate.
"""

NO_RECLASSIFY_ARCHIVES = (
    'econ',  # New September 2017.
)
"""
Don't make auto-proposals for these user-supplied primary archives.

These categories may not be known to the classifier, or the
classifier-suggested alternatives may be consistently innaccurate.
"""

AUTO_CROSS_FOR_PRIMARY = {
    'cs.LG': 'stat.ML',
    'stat.ML': 'cs.LG'
}
"""
When these categories are the primary, a corresponding cross will be suggested.

Per ARXIVOPS-500.
"""
