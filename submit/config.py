import os


MAX_UPLOAD_SIZE = os.environ.get('MAX_UPLOAD_SIZE', 60_000_000)
MAX_BY_REFERENCE_SIZE = os.environ.get('MAX_BY_REFERENCE_SIZE', 120_000_000)
TREATMENT_URI = os.environ.get('TREATMENT_URI', 'https://arxiv.org/help')
COLLECTION_POLICY_URI = os.environ.get('COLLECTION_POLICY_URI',
                                       'https://arxiv.org/help')

JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')
