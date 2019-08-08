"""Helpers for service modules."""

import io
from typing import Callable, Iterator, Any, Optional

from typing_extensions import Literal


class ReadWrapper(io.BytesIO):
    """Wraps a response body streaming iterator to provide ``read()``."""

    def __init__(self, iter_content: Callable[[int], Iterator[bytes]],
                 content_size_bytes: int, size: int = 4096) -> None:
        """Initialize the streaming iterator."""
        self._iter_content = iter_content(size)
        # Must be set for requests to treat this as streamable "file like
        # object".
        # See https://github.com/psf/requests/blob/bedd9284c9646e50c10b3defdf519d4ba479e2c7/requests/models.py#L476
        self.len = content_size_bytes

    def seekable(self) -> Literal[False]:
        """Indicate that this is a non-seekable stream."""
        return False

    def readable(self) -> Literal[True]:
        """Indicate that it *is* a readable stream."""
        return True

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        """
        Read the next chunk of the content stream.

        Arguments are ignored, since the chunk size must be set at the start.
        """
        # print('read with size', size)
        # if size == -1:
        #     return b''.join(self._iter_content)
        return next(self._iter_content)

    def __len__(self) -> int:
        return self.len

    # This must be included for requests to treat this as a streamble
    # "file-like object".
    # See https://github.com/psf/requests/blob/bedd9284c9646e50c10b3defdf519d4ba479e2c7/requests/models.py#L470-L473
    def __iter__(self) -> Iterator[bytes]:
        """Generate chunks of body content."""
        return self._iter_content