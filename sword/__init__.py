"""Base implementation of the SWORDv3 protocol (draft)."""

import warnings
from collections import defaultdict
from typing import Callable, Any, Tuple, List, Union
import json
from pyld import jsonld
from functools import wraps

SWORD = 'http://purl.org/net/sword/terms'
DC = 'http://purl.org/dc/terms'

OK = 200
NOT_FOUND = 404
FORBIDDEN = 403
CREATED = 201
ACCEPTED = 202
NO_CONTENT = 204
MOVED_PERMANENTLY = 301
SEE_OTHER = 303
TEMPORARY_REDIRECT = 307
PERMANENT_REDIRECT = 308
REDIRECT = [MOVED_PERMANENTLY, TEMPORARY_REDIRECT, PERMANENT_REDIRECT]


Response = Tuple[Union[dict, str], int, dict]


class InvalidRequest(RuntimeError):
    """Client request is invalid."""


class InvalidResponse(RuntimeError):
    """Server response is invalid."""


def _unpack_reqs(reqs: list) -> dict:
    """Unpack a response header requirements into a defaultdict."""
    _reqs: defaultdict = defaultdict(list)
    for req in reqs:
        if isinstance(req, tuple):
            _req = list(req)
            for _stat in _req[:-1]:
                _reqs[_stat].append(_req[-1])
        else:
            _reqs['__all__'].append(_req)
    return _reqs


def request(must: list=[], should: list=[], may: list=[],
            schema: str=None) -> Callable:
    """Generate a decorator to enforce required request characteristics."""
    def decorator(func: Callable) -> Callable:
        """Enforce required request characteristics."""
        @wraps(func)
        def wrapper(body: dict, headers: dict, files: dict=None,
                    **extra) -> Any:
            for field in must:
                if field not in headers:
                    raise InvalidRequest('Missing header %s' % field)
            for field in should:
                if field not in headers:
                    raise InvalidRequest('Missing header %s' % field)
            for field in headers:
                if field not in may:
                    warnings.warn('Unexpected header: %s' % field)
            return func(body, headers, files=files, **extra)
        return wrapper
    return decorator


def response(must: list=[], should: list=[], may: list=[],
             success: list=[], error: list=[], schema: str=None) -> Callable:
    """Generate a decorator to enforce response characteristics."""
    _must = _unpack_reqs(must)
    _should = _unpack_reqs(should)
    _may = _unpack_reqs(may)

    def decorator(func: Callable) -> Callable:
        """Enforce required response characteristics."""
        @wraps(func)
        def wrapper(body: dict, headers: dict, files: dict=None,
                    **extra) -> Any:
            r_body, r_stat, r_head = func(body, headers, files=files, **extra)

            if r_stat not in success:
                if r_stat not in error:
                    raise InvalidResponse('Invalid status code %i' % r_stat)
                return r_body, r_stat, r_head
            for field in set(_must['__all__'] + _must[r_stat]):
                if field not in r_head:
                    raise InvalidResponse('Missing header %s' % field)
            for field in _should['__all__'] + _should[r_stat]:
                if field not in r_head:
                    raise InvalidResponse('Missing header %s' % field)
            for field in headers:
                if field not in _may['__all__'] + _may[r_stat]:
                    warnings.warn('Unexpected header: %s' % field)
            return r_body, r_stat, r_head
        return wrapper
    return decorator


class SWORDBase(object):
    """Base class for SWORD protocol."""

    version = '3'
    """Version of the SWORD protocol that this module implements."""

    context = {'sword': SWORD, 'dc': DC}
    """Namespace for JSON-LD."""

    fields: List[Tuple[str, str]] = []
    required: List[Tuple[str, str]] = []

    def __init__(self, manifold):
        """Set configurable parameters."""
        self.enforce_should = True    # TODO: Do something different here...
        self.manifold = manifold

    def _compact(self, doc: dict, **context) -> dict:
        """Produce a compact JSON-LD document."""
        context.update(self.context)
        return jsonld.compact(doc, context)

    def _fmt(self, namespace: str, field: str) -> str:
        """Format a full URI for a ``field`` in a ``namespace```."""
        base_uri = self.context.get(namespace)
        if not base_uri:
            return field
        return '%s/%s' % (base_uri, field)

    def url_for(self, resource_type: str, **kwargs) -> str:
        """Generate a URI for a resource."""
        raise NotImplemented('url_for must be implemented by a subclass')

    def render(self, body, status, headers) -> Response:
        """Generate a JSON-LD representation of the response."""
        if status is NO_CONTENT:    # Nothing to do.
            return '', status, headers
        data = {}
        for ns, field in self.fields:
            value = body.get(field)
            if value or (ns, field) in self.required:
                data[self._fmt(ns, field)] = value
        return self._compact(data), status, headers


class SWORDSubmission(SWORDBase):
    """Submission package, which includes metadata and (optionally) content."""

    @response(success=[OK, *REDIRECT, SEE_OTHER], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')], schema='schema/status.json')
    @request(may=['Authorization', 'On-Behalf-Of'])
    def get(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Retrieve submission information/status."""
        return self.render(
            *self.manifold.get_status(data, headers, **extra)
        )

    @response(success=[OK, ACCEPTED, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=['Location'], schema='schema/status.json')
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'Packaging'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress'])
    def post(self, data: dict, headers: dict, files: dict=None,
             **extra) -> Response:
        """Add content or other file to submission."""
        return self.render(
            *self.manifold.add_content(data, headers, files, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def delete(self, data: dict, headers: dict, files: dict=None,
               **extra) -> Response:
        """Delete submission."""
        return self.render(
            *self.manifold.delete_submission(data, headers, **extra)
        )


class SWORDMetadata(SWORDBase):
    """Submission metadata."""

    @response(success=[OK, *REDIRECT, SEE_OTHER], error=[NOT_FOUND, FORBIDDEN],
              should=[(OK, 'MetadataFormat')],
              must=[(*REDIRECT, SEE_OTHER, 'Location')],
              schema='schema/metadata.json')
    @request(may=['Authorization', 'On-Behalf-Of', 'Accept-MetadataFormat'])
    def get(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Retrieve submission metadata."""
        return self.render(
            *self.manifold.get_metadata(data, headers, files, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'MetadataFormat'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress'],
             schema='schema/metadata.json')
    def post(self, data: dict, headers: dict, files: dict=None,
             **extra) -> Response:
        """Add or update submission metadata."""
        return self.render(
            *self.manifold.update_metadata(data, headers, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'MetadataFormat'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress'],
             schema='schema/metadata.json')
    def put(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Replace submission metadata."""
        return self.render(
            *self.manifold.update_metadata(data, headers, **extra)
        )


class SWORDContent(SWORDBase):
    """Submission content package, which may contain multiple files."""

    @response(success=[OK, *REDIRECT, SEE_OTHER], error=[NOT_FOUND, FORBIDDEN],
              should=['Packaging'], must=[(*REDIRECT, SEE_OTHER, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of', 'Accept-Packaging'])
    def get(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Retrieve content as package."""
        return self.render(*self.manifold.get_content(data, headers, **extra))

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type'], should=['Content-Length', 'Digest'],
             may=['Authorization', 'On-Behalf-Of'])
    def post(self, data: dict, headers: dict, files: dict=None,
             **extra) -> Response:
        """Add file to submission content."""
        return self.render(
            *self.manifold.add_file(data, headers, files, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'Packaging'],
             may=['Authorization', 'On-Behalf-Of'])
    def put(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Replace object content."""
        return self.render(
            *self.manifold.update_content(data, headers, files, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def delete(self, data: dict, headers: dict, files: dict=None,
               **extra) -> Response:
        """Delete submission content package."""
        return self.render(
            *self.manifold.delete_content(data, headers, **extra)
        )


class SWORDFile(SWORDBase):
    """Submission content file."""

    @response(success=[OK, *REDIRECT, SEE_OTHER], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, SEE_OTHER, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def get(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Retrieve individual file from submission."""
        return self.render(
            *self.manifold.get_file(data, headers, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type'], should=['Content-Length', 'Digest'],
             may=['Authorization', 'On-Behalf-Of'])
    def put(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Replace individual content file."""
        return self.render(
            *self.manifold.update_file(data, headers, files, **extra)
        )

    @response(success=[NO_CONTENT, *REDIRECT], error=[NOT_FOUND, FORBIDDEN],
              must=[(*REDIRECT, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def delete(self, data: dict, headers: dict, files: dict=None,
               **extra) -> Response:
        """Delete individual content file."""
        return self.render(
            *self.manifold.delete_file(data, headers, **extra)
        )


class SWORDCollection(SWORDBase):
    """Repository collection."""

    fields = [
        ('sword', 'version'),
        ('sword', 'maxUploadSize'),
        ('sword', 'maxByReferenceSize'),
        ('sword', 'name'),
        ('sword', 'accept'),
        ('sword', 'collectionPolicy'),
        ('sword', 'treatment'),
        ('sword', 'by-reference'),
        ('sword', 'in-progress'),
        ('sword', 'digest'),
        ('sword', 'mediation'),
        ('sword', 'collections')
    ]
    required = [
        ('sword', 'version'),
        ('sword', 'name'),
        ('sword', 'collections'),
    ]

    @response(success=[CREATED, ACCEPTED], error=[NOT_FOUND, FORBIDDEN],
              must=['Location'])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'MetadataFormat',
                     'Packaging'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress', 'Slug'])
    def post(self, data: dict, headers: dict, files: dict=None,
             **extra) -> Response:
        """Deposit new object with metadata, and (optionally) content."""
        return self.render(
            *self.manifold.add_submission(data, headers, files, **extra)
        )


class SWORDServiceDocument(SWORDBase):
    """SWORD service document."""

    fields = [
        ('sword', 'version'),
        ('sword', 'maxUploadSize'),
        ('sword', 'maxByReferenceSize'),
        ('sword', 'name'),
        ('sword', 'accept'),
        ('sword', 'collectionPolicy'),
        ('sword', 'treatment'),
        ('sword', 'by-reference'),
        ('sword', 'in-progress'),
        ('sword', 'digest'),
        ('sword', 'mediation'),
        ('sword', 'collections')
    ]
    required = [
        ('sword', 'version'),
        ('sword', 'name'),
        ('sword', 'collections'),
    ]

    @property
    def collections(self) -> list:
        """List of collections available for deposit."""
        return [self.manifold.collection.render(**cdata)
                for cdata in self.manifold.list_collections()]

    @response(success=[OK], error=[NOT_FOUND, FORBIDDEN])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def get(self, data: dict, headers: dict, files: dict=None,
            **extra) -> Response:
        """Generate the service document for this submission endpoint."""
        body, status, r_head = self.manifold.get_service(data, headers,
                                                         **extra)
        body.update({'collections': self.collections})
        return self.render(body, status, r_head)


class SWORDService(object):
    """
    Interface for a service that implements SWORD.

    The methods on this interface (``add_*``, ``delete_*``, ``update_``,
    ``get_*``, etc.) are provided as hooks for the implementing service.
    """
    ServiceDocument = SWORDServiceDocument
    Collection = SWORDCollection
    Submission = SWORDSubmission
    Metadata = SWORDMetadata
    Content = SWORDContent
    File = SWORDFile

    def __init__(self):
        self.serviceDocument = self.ServiceDocument()
        self.collection = self.Collection()
        self.submission = self.Submission()
        self.metadata = self.Metadata()
        self.content = self.Content()
        self.file = self.File()

    def list_collections(self) -> list:
        """Hook used to retrieve data about collections in this service."""
        raise NotImplemented('Subclass must implement get_collections()')

    def get_service(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for retriving service information."""
        raise NotImplemented('Subclass must implement get_service()')

    def add_submission(self, body: dict, headers: dict, files: dict,
                       **extra) -> Response:
        """Hook for creating a new submission."""
        raise NotImplemented('Subclass must implement add_submission()')

    def delete_submission(self, body: dict, headers: dict,
                          **extra) -> Response:
        """Hook for deleting a submission."""
        raise NotImplemented('Subclass must implement delete_submission()')

    def get_metadata(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for getting submission metadata."""
        raise NotImplemented('Subclass must implement get_metadata()')

    def update_metadata(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for updating submission metadata."""
        raise NotImplemented('Subclass must implement update_metadata()')

    def add_file(self, body: dict, headers: dict, files: dict,
                 **extra) -> Response:
        """Hook for adding a file to submission content."""
        raise NotImplemented('Subclass must implement add_file()')

    def get_file(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for getting an individual file from submission content."""
        raise NotImplemented('Subclass must implement get_file()')

    def update_file(self, body: dict, headers: dict, files: dict,
                    **extra) -> Response:
        """Hook for adding or updating a file in submission content."""
        raise NotImplemented('Subclass must implement update_file()')

    def delete_file(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for deleting a file from submission content."""
        raise NotImplemented('Subclass must implement delete_file()')

    def get_status(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for getting the status of a submission."""
        raise NotImplemented('Subclass must implement add_submission()')

    def add_content(self, body: dict, headers: dict, files: dict,
                    **extra) -> Response:
        """Hook for adding a file to submission content."""
        raise NotImplemented('Subclass must implement add_content()')

    def get_content(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for getting submission content."""
        raise NotImplemented('Subclass must implement get_content()')

    def update_content(self, body: dict, headers: dict,
                       files: dict, **extra) -> Response:
        """Hook for updating entire submission content package."""
        raise NotImplemented('Subclass must implement update_content()')

    def delete_content(self, body: dict, headers: dict, **extra) -> Response:
        """Hook for deleting entire submission content package."""
        raise NotImplemented('Subclass must implement delete_content()')
