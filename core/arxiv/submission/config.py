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

CLASSIC_DATABASE_URI = os.environ.get('CLASSIC_DATABASE_URI', 'sqlite:///')

ENABLE_ASYNC = os.environ.get('ENABLE_ASYNC', '0')
"""
If ``1``, asynchronous callbacks will be dispatched to the worker.

Otherwise they will be executed in the thread in which they are called.
"""

ENABLE_CALLBACKS = os.environ.get('ENABLE_CALLBACKS', '0')
"""If ``0``, callbacks bound to events will not be executed."""


CORE_VERSION = "0.0.0"
