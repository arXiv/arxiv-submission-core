from unittest import mock


def raise_http_exception(exc, code: int, msg='argle bargle'):
    def side_effect(*args, **kwargs):
        raise exc(msg, mock.MagicMock(status_code=code))
    return side_effect
