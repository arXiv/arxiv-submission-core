"""Submission core configuration parameters."""

import os
from kombu.serialization import register
from .serializer import dumps, loads

register('process-json', dumps, loads,
         content_type='application/x-process-json',
         content_encoding='utf-8')

APPLY_RULES = bool(int(os.environ.get('APPLY_RULES', '1')))
BROKER_URL = os.environ.get('SUBMISSION_AGENT_BROKER_URL',
                            'redis://localhost:6379/0')
RESULT_BACKEND = os.environ.get('SUBMISSION_AGENT_RESULT_BACKEND', BROKER_URL)
QUEUE_NAME_PREFIX = os.environ.get('SUBMISSION_AGENT_QUEUE_NAME_PREFIX',
                                   'submission-agent-')
PREFETCH_MULTIPLIER = int(os.environ.get(
    'SUBMISSION_AGENT_WORKER_PREFETCH_MULTIPLIER',
    '1'
))
TASK_ACKS_LATE = bool(int(os.environ.get('SUBMISSION_AGENT_TASK_ACKS_LATE', '1')))

CELERY_ACCEPT_CONTENT = ['process-json']
CELERY_TASK_SERIALIZER = 'process-json'
CELERY_RESULT_SERIALIZER = 'process-json'

FILE_MANAGER_HOST = os.environ.get('FILE_MANAGER_HOST', 'arxiv.org')
FILE_MANAGER_PORT = os.environ.get('FILE_MANAGER_PORT', '443')
FILE_MANAGER_PROTO = os.environ.get('FILE_MANAGER_PROTO', 'https')
FILE_MANAGER_PATH = os.environ.get('FILE_MANAGER_PATH', '')
FILE_MANAGER_ENDPOINT = os.environ.get(
    'FILE_MANAGER_ENDPOINT',
    f'{FILE_MANAGER_PROTO}://{FILE_MANAGER_HOST}:{FILE_MANAGER_PORT}/{FILE_MANAGER_PATH}'
)
FILE_MANAGER_VERIFY = bool(int(os.environ.get('FILE_MANAGER_VERIFY', '1')))

COMPILER_HOST = os.environ.get('COMPILER_HOST', 'arxiv.org')
COMPILER_PORT = os.environ.get('COMPILER_PORT', '443')
COMPILER_PROTO = os.environ.get('COMPILER_PROTO', 'https')
COMPILER_PATH = os.environ.get('COMPILER_PATH', '')
COMPILER_ENDPOINT = os.environ.get(
    'COMPILER_ENDPOINT',
    f'{COMPILER_PROTO}://{COMPILER_HOST}:{COMPILER_PORT}/{COMPILER_PATH}'
)
COMPILER_VERIFY = bool(int(os.environ.get('COMPILER_VERIFY', '1')))

CLASSIFIER_ENDPOINT = os.environ.get('CLASSIFIER_ENDPOINT', 'http://localhost:8000')
CLASSIFIER_VERIFY = bool(int(os.environ.get('CLASSIFIER_VERIFY', '0')))

ENABLE_ASYNC = os.environ.get('ENABLE_ASYNC', '0')
"""
If ``1``, asynchronous callbacks will be dispatched to the worker.

Otherwise they will be executed in the thread in which they are called.
"""

ENABLE_CALLBACKS = os.environ.get('ENABLE_CALLBACKS', '0')
"""If ``0``, callbacks bound to events will not be executed."""

JWT_SECRET = os.environ.get('JWT_SECRET')

CORE_VERSION = "0.0.0"

# Email notification configuration.
EMAIL_ENABLED = bool(int(os.environ.get('EMAIL_ENABLED', '1')))
DEFAULT_SENDER = os.environ.get('DEFAULT_SENDER', 'noreply@arxiv.org')
SUPPORT_EMAIL = "help@arxiv.org"
SMTP_HOSTNAME = os.environ.get('SMTP_HOSTNAME', 'localhost')
SMTP_USERNAME = os.environ.get('SMTP_USERNAME', 'foouser')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'foopass')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '0'))
SMTP_LOCAL_HOSTNAME = os.environ.get('SMTP_LOCAL_HOSTNAME', None)
SMTP_SSL = bool(int(os.environ.get('SMTP_SSL', '0')))


EXTERNAL_URL_SCHEME = os.environ.get('EXTERNAL_URL_SCHEME', 'https')
BASE_SERVER = os.environ.get('BASE_SERVER', 'arxiv.org')
SERVER_NAME = "submit.arxiv.org"

URLS = [
    ("submission", "/<int:submission_id>", "submit.arxiv.org"),
    ("confirmation", "/<int:submission_id>/confirmation", "submit.arxiv.org")
]
"""
URLs for external services, for use with :func:`flask.url_for`.
This subset of URLs is common only within submit, for now - maybe move to base
if these pages seem relevant to other services.

For details, see :mod:`arxiv.base.urls`.
"""


MAX_SAVE_RETRIES = 25
DEFAULT_SAVE_RETRY_DELAY = 30


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
LINENOS_LIMIT = 0

TITLE_SIMILARITY_WINDOW = 3*365/12    # days
TITLE_SIMILARITY_THRESHOLD = 0.7
METADATA_ASCII_THRESHOLD = 0.5


COMPRESSED_PACKAGE_MAX = 6_000_000
UNCOMPRESSED_PACKAGE_MAX = 18_000_000
PDF_LIMIT = 15_000_000
"""The maximum size of the resulting PDF."""

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
When these categories are the primary, a corresponding cross be suggested.

Per ARXIVOPS-500.
"""

# AWS credentials.
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'nope')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'nope')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')


KINESIS_STREAM = os.environ.get("KINESIS_STREAM", "SubmissionEvents")
KINESIS_SHARD_ID = os.environ.get("KINESIS_SHARD_ID", "0")
KINESIS_START_TYPE = os.environ.get("KINESIS_START_TYPE", "TRIM_HORIZON")
KINESIS_ENDPOINT = os.environ.get("KINESIS_ENDPOINT", None)
KINESIS_VERIFY = bool(int(os.environ.get("KINESIS_VERIFY", "1")))

LOGLEVEL = int(os.environ.get('LOGLEVEL', '10'))

CLASSIC_DATABASE_URI = os.environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')
SQLALCHEMY_DATABASE_URI = CLASSIC_DATABASE_URI
SQLALCHEMY_TRACK_MODIFICATIONS = False
SQLALCHEMY_BINDS = {
    'agent': os.environ.get('SUBMISSION_AGENT_DATABASE_URI')
}

WAIT_FOR_SERVICES = bool(int(os.environ.get('WAIT_FOR_SERVICES', '0')))
WAIT_ON_STARTUP = int(os.environ.get('WAIT_ON_STARTUP', '0'))
