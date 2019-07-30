"""Request controllers."""

from typing import Dict, Any, Tuple, Optional, IO
from http import HTTPStatus

from werkzeug.exceptions import NotFound, BadRequest, InternalServerError
from werkzeug.datastructures import FileStorage

from . import store

Response = Tuple[Dict[str, Any], HTTPStatus, Dict[str, str]]


def service_status() -> Response:
    """Handle requests for the status of this service."""
    if not store.is_available():
        raise InternalServerError('Cannot access legacy filesystem')
    return {}, HTTPStatus.OK, {}


def deposit_source(submission_id: int, content: IO[bytes]) -> Response:
    """
    Deposit the source package for a submission.

    Parameters
    ----------
    submission_id : int
        Numeric submission identifier.
    content : IO
        A streaming bytes IO from the request body.

    Returns
    -------
    dict
        Data for the response body.
    int
        HTTP response status code.
    dict
        Headers to add to the response.

    """
    try:
        store.store_source(submission_id, content)
    except RuntimeError as e:
        raise InternalServerError(f'Could not store source: {e}') from e
    headers = {'ETag': store.get_source_checksum(submission_id)}
    return {}, HTTPStatus.CREATED, headers


def check_source_exists(submission_id: int) -> Response:
    """
    Determine whether or not the source package for a submission exists.

    Response includes the source package checksum in the ``ETag`` header, for
    verification.

    Parameters
    ----------
    submission_id : int
        Numeric submission identifier.
    content : :class:`FileStorage` or None.

    Returns
    -------
    dict
        Data for the response body.
    int
        HTTP response status code.
    dict
        Headers to add to the response.

    """
    if not store.does_source_exist(submission_id):
        raise NotFound(f'No source for submission: {submission_id}')
    headers = {'ETag': store.get_source_checksum(submission_id)}
    return {}, HTTPStatus.OK, headers


def deposit_preview(submission_id: int, content: IO[bytes]) -> Response:
    """
    Deposit the PDF preview for a submission.

    Parameters
    ----------
    submission_id : int
        Numeric submission identifier.
    content : IO
        A streaming bytes IO from the request body.

    Returns
    -------
    dict
        Data for the response body.
    int
        HTTP response status code.
    dict
        Headers to add to the response.

    """
    try:
        store.store_preview(submission_id, content)
    except RuntimeError as e:
        raise InternalServerError(f'Could not store preview: {e}') from e
    headers = {'ETag': store.get_preview_checksum(submission_id)}
    return {}, HTTPStatus.CREATED, headers


def check_preview_exists(submission_id: int) -> Response:
    """
    Determine whether or not the PDF preview for a submission exists.

    Response includes the PDF checksum in the ``ETag`` header, for
    verification.

    Parameters
    ----------
    submission_id : int
        Numeric submission identifier.
    content : :class:`FileStorage` or None.

    Returns
    -------
    dict
        Data for the response body.
    int
        HTTP response status code.
    dict
        Headers to add to the response.

    """
    if not store.does_preview_exist(submission_id):
        raise NotFound(f'No preview for submission: {submission_id}')
    headers = {'ETag': store.get_preview_checksum(submission_id)}
    return {}, HTTPStatus.OK, headers
