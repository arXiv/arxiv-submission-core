from flask import url_for
from sword import SWORDController

ARXIV = 'http://arxiv.org/schema/terms'


class ArXivSWORDController(SWORDController):
    def __init__(self, **config):
        super(ArXivSWORDController, self).__init__(**config)
        self.context.update({'arxiv': ARXIV})

    def url_for(self, route, **kwargs):
        return url_for('submit.%s' % route, **kwargs)
