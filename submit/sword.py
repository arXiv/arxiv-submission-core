import json
from pyld import jsonld
from flask import url_for

SWORD = 'http://purl.org/net/sword/terms'
ARXIV = 'http://arxiv.org/schema/terms'
DC = 'http://purl.org/dc/terms'
CONTEXT = {
    'sword': SWORD,
    'arxiv': ARXIV,
    'dc': DC
}

def _compact(doc: dict, **context) -> dict:
    """Produce a compact JSON-LD document."""
    context.update(CONTEXT)
    return jsonld.compact(doc, context)


def render_service_document(config: dict) -> dict:
    """Generate the service document for this submission endpoint."""
    return _compact({
        '%s/version' % SWORD: "3",
        '%s/maxUploadSize' % SWORD: config.get('MAX_UPLOAD_SIZE'),
        '%s/maxByReferenceSize' % SWORD: config.get('MAX_BY_REFERENCE_SIZE'),
        '%s/maxByReferenceSize' % SWORD: config.get('MAX_BY_REFERENCE_SIZE'),
        '%s/name' % SWORD: 'arXiv',
        '%s/accept' % SWORD: ['application/json'],
        '%s/collectionPolicy' % SWORD: config.get('COLLECTION_POLICY_URI'),
        '%s/treatment' % SWORD: config.get('TREATMENT_URI'),
        '%s/by-reference' % SWORD: config.get('ALLOW_BY_REFERENCE'),
        '%s/in-progress' % SWORD: config.get('ALLOW_IN_PROGRESS'),
        '%s/digest' % SWORD: config.get('DIGEST_ALGORITHM'),
        '%s/mediation' % SWORD: config.get('ALLOW_MEDIATION'),
        '%s/collections' % SWORD: [
            url_for('submit.collection', archive=cname)
            for cname in config.get('COLLECTIONS')
        ]
    })
