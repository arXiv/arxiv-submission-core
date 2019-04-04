"""Submission core configuration parameters."""

import os
from kombu.serialization import register
from .serializer import dumps, loads

register('ejson', dumps, loads,
         content_type='application/x-ejson',
         content_encoding='utf-8')

APPLY_RULES = bool(int(os.environ.get('APPLY_RULES', '1')))
BROKER_URL = os.environ.get('SUBMISSION_BROKER_URL', 'redis://localhost:6379/0')
RESULT_BACKEND = os.environ.get('SUBMISSION_RESULT_BACKEND', BROKER_URL)
QUEUE_NAME_PREFIX = os.environ.get('SUBMISSION_QUEUE_NAME_PREFIX',
                                   'submission-')
PREFETCH_MULTIPLIER = int(os.environ.get(
    'SUBMISSION_WORKER_PREFETCH_MULTIPLIER',
    '1'
))
TASK_ACKS_LATE = bool(int(os.environ.get('SUBMISSION_TASK_ACKS_LATE', '1')))

CELERY_ACCEPT_CONTENT = ['ejson']
CELERY_TASK_SERIALIZER = 'ejson'
CELERY_RESULT_SERIALIZER = 'ejson'


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

CLASSIC_DATABASE_URI = os.environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')
SQLALCHEMY_DATABASE_URI = CLASSIC_DATABASE_URI
SQLALCHEMY_TRACK_MODIFICATIONS = False

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

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'nope')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'nope')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
KINESIS_STREAM = os.environ.get("KINESIS_STREAM", "SubmissionMetadata")
KINESIS_SHARD_ID = os.environ.get("KINESIS_SHARD_ID", "0")
KINESIS_START_TYPE = os.environ.get("KINESIS_START_TYPE", "TRIM_HORIZON")
KINESIS_ENDPOINT = os.environ.get("KINESIS_ENDPOINT", None)
KINESIS_VERIFY = bool(int(os.environ.get("KINESIS_VERIFY", "1")))

LOGLEVEL = int(os.environ.get('LOGLEVEL', '40'))
