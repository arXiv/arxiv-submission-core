from typing import Callable, Tuple, Any
from functools import wraps
from werkzeug.exceptions import BadRequest
from arxiv.util import schema


Response = Tuple[dict, int, dict]


def validate_request(schema_path: str) -> Callable:
    """
    Generate a route decorator that validates the request body.

    Parameters
    ----------
    schema_path : str
        Path (absolute, or relative to the execution path) to the JSON Schema
        document.
    Returns
    -------
    decorator
        Decorates a controller function with request body validation against
        the specified JSON Schema.


    """
    validate = schema.load(schema_path)

    def _decorator(func: Callable) -> Callable:
        @wraps(func)
        def _wrpr(data: dict, *args: Any, **kwargs: Any) -> Response:
            try:
                validate(data)
            except schema.ValidationError as e:
                # A summary of the exception is on the first line of the repr.
                msg = str(e).split('\n')
                detail = {
                    'reason': f'Metadata validation failed: {msg[0]}',
                    'detail': ' '.join(msg)
                }
                raise BadRequest(msg[0], detail)
            response: Tuple[dict, int, dict] = func(data, *args, **kwargs)
            return response
        return _wrpr
    return _decorator
