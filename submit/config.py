import os


MAX_UPLOAD_SIZE = os.environ.get('MAX_UPLOAD_SIZE', 60_000_000)
MAX_BY_REFERENCE_SIZE = os.environ.get('MAX_BY_REFERENCE_SIZE', 120_000_000)
TREATMENT_URI = os.environ.get('TREATMENT_URI', 'https://arxiv.org/help')
COLLECTION_POLICY_URI = os.environ.get(
    'COLLECTION_POLICY_URI',
    'https://arxiv.org/help/third_party_submission'
)
ALLOW_BY_REFERENCE = os.environ.get('ALLOW_BY_REFERENCE', False)
ALLOW_IN_PROGRESS = os.environ.get('ALLOW_IN_PROGRESS', True)
ALLOW_MEDIATION = os.environ.get('ALLOW_MEDIATION', True)
DIGEST_ALGORITHM = os.environ.get('DIGEST_ALGORITHM', 'md5')

COLLECTIONS = ['physics', 'math', 'cs', 'q-bio', 'q-fin', 'stat', 'eess',
               'econ']


JWT_SECRET = os.environ.get('JWT_SECRET', 'foo')
