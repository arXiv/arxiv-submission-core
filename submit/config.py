"""
Flask configuration.

Docstrings are from the `Flask configuration documentation
<http://flask.pocoo.org/docs/0.12/config/>`_.
"""
import os

ON = 'yes'
OFF = 'no'

DEBUG = os.environ.get('DEBUG') == ON
"""enable/disable debug mode"""

TESTING = os.environ.get('TESTING') == ON
"""enable/disable testing mode"""

PROPAGATE_EXCEPTIONS = \
    True if os.environ.get('PROPAGATE_EXCEPTIONS') == ON else None
"""
explicitly enable or disable the propagation of exceptions. If not set or
explicitly set to None this is implicitly true if either TESTING or DEBUG is
true.
"""

PRESERVE_CONTEXT_ON_EXCEPTION = \
    True if os.environ.get('PRESERVE_CONTEXT_ON_EXCEPTION') == ON else None
"""
By default if the application is in debug mode the request context is not
popped on exceptions to enable debuggers to introspect the data. This can be
disabled by this key. You can also use this setting to force-enable it for non
debug execution which might be useful to debug production applications (but
also very risky).
"""

USE_X_SENDFILE = os.environ.get('USE_X_SENDFILE') == ON
"""Enable/disable x-sendfile"""

LOGGER_NAME = os.environ.get('LOGGER_NAME', 'search')
"""The name of the logger."""

LOGGER_HANDLER_POLICY = os.environ.get('LOGGER_HANDLER_POLICY', 'debug')
"""
the policy of the default logging handler. The default is 'always' which means
that the default logging handler is always active. 'debug' will only activate
logging in debug mode, 'production' will only log in production and 'never'
disables it entirely.
"""

SERVER_NAME = os.environ.get('SEARCH_SERVER_NAME', None)
"""
the name and port number of the server. Required for subdomain support
(e.g.: 'myapp.dev:5000') Note that localhost does not support subdomains so
setting this to 'localhost' does not help. Setting a SERVER_NAME also by
default enables URL generation without a request context but with an
application context.
"""

APPLICATION_ROOT = os.environ.get('APPLICATION_ROOT', None)
"""
If the application does not occupy a whole domain or subdomain this can be set
to the path where the application is configured to live. This is for session
cookie as path value. If domains are used, this should be None.
"""
