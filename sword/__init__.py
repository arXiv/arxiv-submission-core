"""
Base implementation of the SWORDv3 protocol (draft).

This module is responsible for the baseline request semantics and validation,
and speaks JSON-LD.
"""

import os
import copy
import warnings
from collections import defaultdict
from typing import Callable, Any, Tuple, List, Union
import json
import jsonschema
from functools import wraps, partial, update_wrapper
from itertools import chain
from pyld import jsonld
from pyld.jsonld import JsonLdError

SWORD = 'http://purl.org/net/sword/terms/'
DC = 'http://purl.org/dc/terms/'

OK = 200
BAD_REQUEST = 400
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


SWORDRequest = Tuple[dict, dict, dict, dict]
SWORDResponse = Tuple[Union[dict, str], int, dict]


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
            _reqs['__all__'].append(req)
    return _reqs


class SWORDBaseEndpoint(object):
    """Base class for SWORD protocol."""

    version = '3'
    """Version of the SWORD protocol that this module implements."""

    context = {'sword': SWORD, 'dc': DC}
    """Namespace for JSON-LD."""

    fields: List[Tuple[str, str]] = []
    required: List[Tuple[str, str]] = []

    def _compact(self, doc: dict, **context) -> dict:
        """Produce a compact JSON-LD document."""
        context.update(self.context)
        return jsonld.compact(doc, context)

    def _fmt(self, namespace: str, field: str) -> str:
        """Format a full URI for a ``field`` in a ``namespace```."""
        base_uri = self.context.get(namespace)
        if not base_uri:
            return field
        return '%s/%s' % (base_uri.rstrip('/'), field.lstrip('/'))

    def _iterfmt(self, value: Any) -> Any:
        if type(value) is list:
            return [self._iterfmt(item) for item in value]
        elif type(value) is dict:
            return {
                self._fmt(*k) if type(k) is tuple else k: self._iterfmt(v)
                for k, v in value.items()
            }
        return value

    def unpack(self, req: SWORDRequest) -> SWORDRequest:
        """Expand a JSON-LD payload."""
        body, headers, files, extra = req
        try:
            body = jsonld.expand(body)
        except JsonLdError:
            pass
        return body, headers, files, extra

    def pack(self, response: SWORDResponse) -> SWORDResponse:
        """Generate a JSON-LD representation of the response."""
        body, status, headers = response
        if body is None:
            body = {}
        if status is NO_CONTENT:    # Nothing to do.
            response[0] = ''
            return response
        data = {}
        for field in self.fields:
            value = body.get(field)
            if value is not None or field in self.required:
                data[field] = value
        return self._compact(self._iterfmt(data)), status, headers


class ProtocolDecorator(object):
    """
    Base class for protocol decorators.

    In order to decorate instance methods, we need to obtain a reference to
    the instance itself. This is achieved by implementing the __get__
    descriptor method.
    """

    def __init__(self, func):
        """Set reference to decorated function."""
        self.func = func

    def __get__(self, instance, owner):
        """Obtain the instance for which the decorated function is a method."""
        return partial(self.__call__, instance)

    @property
    def request(self):
        """Proxy :prop:`.request` on the decorated function, if set."""
        return getattr(self.func, 'request')

    @property
    def response(self):
        """Proxy :prop:`.response` on the decorated function, if set."""
        return getattr(self.func, 'response')


class RequestDecorator(ProtocolDecorator):
    request = {}

    def unpack(self, req: SWORDRequest) -> SWORDRequest:
        """Expand a JSON-LD payload."""
        body, headers, files, extra = req
        try:
            body = jsonld.expand(body)
        except JsonLdError:
            pass
        return body, headers, files, extra

    def _validate(self, body: dict) -> None:
        if self.request['schema']:
            if os.path.exists(self.request['schema']):
                schema = json.load(open(self.request['schema']))
                try:
                    jsonschema.validate(body, schema)
                except jsonschema.exceptions.ValidationError as e:
                    raise
                    raise ValueError('Invalid request') from e

    def __call__(self, inst: SWORDBaseEndpoint, request: SWORDRequest) -> Any:
        """Perform request validation and call the wrapped instance method."""
        body, headers, files, extra = self.unpack(request)
        try:
            self._validate(body)
        except ValueError:
            return {'reason': 'Schema validation failed'}, BAD_REQUEST, {}

        for field in self.request['must']:
            if field not in headers:
                err = {'reason': 'Missing header %s' % field}
                return err, BAD_REQUEST, {}

        for field in self.request['should']:
            if field not in headers:
                warnings.warn('Missing header %s' % field, RuntimeWarning)
        required = set(self.request['should'] + self.request['must'])
        for field in set(headers) - required:
            if field not in self.request['may']:
                warnings.warn('Unexpected header: %s' % field,
                              RuntimeWarning)
        return self.func(inst, request)


class ResponseDecorator(ProtocolDecorator):
    response = {}

    _seen = []

    def _may_headers(self, r_status: int) -> List[str]:
        _may = self.response['may']
        return _may['__all__'] + _may[r_status] + self._seen

    def _should_headers(self, r_status: int) -> List[str]:
        _should = self.response['should']
        return _should['__all__'] + _should[r_status]

    def _must_headers(self, r_status: int) -> List[str]:
        _must = self.response['must']
        return _must['__all__'] + _must[r_status]

    def __call__(self, inst: SWORDBaseEndpoint, request: SWORDRequest) -> Any:
        """Call the wrapped instance method and perform response validation."""
        r_body, r_stat, r_head = self.func(inst, request)
        _seen = []
        print(r_body, r_stat, r_head, self.response['success'])
        if r_stat not in self.response['success']:
            if r_stat not in self.response['error']:
                raise InvalidResponse('Invalid status code %i' % r_stat)
            return r_body, r_stat, r_head
        for field in self._must_headers(r_stat):
            _seen.append(field)
            if field not in r_head:
                raise InvalidResponse('Missing header %s' % field)
        for field in self._should_headers(r_stat):
            _seen.append(field)
            if field not in r_head:
                warnings.warn('Missing header %s' % field, RuntimeWarning)
        for field in r_head.keys():
            if field not in self._may_headers(r_stat):
                warnings.warn('Unexpected header: %s' % field,
                              RuntimeWarning)
        return r_body, r_stat, r_head


def response(must: list=[], should: list=[], may: list=[], success: list=[OK],
             error: list=[NOT_FOUND, FORBIDDEN, BAD_REQUEST],
             schema: str=None):
    """Generate a decorator to enforce response characteristics."""
    # decorator = copy.deepcopy(ResponseDecorator)
    decorator = type('DynamicResponseDecorator', (ResponseDecorator,),
                     {
                        'response': {
                            'must': _unpack_reqs(must),
                            'should': _unpack_reqs(should),
                            'may': _unpack_reqs(may),
                            'success': success,
                            'error': error,
                            'schema': schema
                        }
                     })

    return decorator


def request(must: list=[], should: list=[], may: list=[], schema: str=None):
    """Generate a decorator to enforce required request characteristics."""
    decorator = type('DynamicRequestDecorator', (RequestDecorator,),
                     {
                         'request': {
                             'must': must,
                             'should': should,
                             'may': may,
                             'schema': schema
                         }
                     })
    return decorator


class SWORDSubmission(SWORDBaseEndpoint):
    """Submission package, which includes metadata and (optionally) content."""

    __endpoint__ = 'submission'

    @request(may=['Authorization', 'On-Behalf-Of'])
    @response(success=[OK, *REDIRECT, SEE_OTHER],
              must=[(*REDIRECT, 'Location')], schema='schema/status.json')
    def get_status(self, req: SWORDRequest) -> SWORDResponse:
        """Retrieve submission information/status."""
        return self.pack(self._get_status(*req))

    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'Packaging'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress'])
    @response(success=[OK, ACCEPTED, *REDIRECT],
              must=['Location'], schema='schema/status.json')
    def add_content(self, req: SWORDRequest) -> SWORDResponse:
        """Add content or other file to submission."""
        return self.pack(self._add_content(*req))

    @request(may=['Authorization', 'On-Behalf-Of'])
    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    def delete_submission(self, req: SWORDRequest) -> SWORDResponse:
        """Delete submission."""
        return self.pack(self._delete_submission(*req))

    @property
    def methods(self):
        """HTTP methods supported by this endpoint."""
        return {
            'GET': self.get_status,
            'DELETE': self.delete_submission,
            'POST': self.add_content,
        }


class SWORDMetadata(SWORDBaseEndpoint):
    """Submission metadata."""

    __endpoint__ = 'metadata'

    @response(success=[OK, *REDIRECT, SEE_OTHER],
              should=[(OK, 'MetadataFormat')],
              must=[(*REDIRECT, SEE_OTHER, 'Location')],
              schema='schema/metadata.json')
    @request(may=['Authorization', 'On-Behalf-Of', 'Accept-MetadataFormat'])
    def get_metadata(self, req: SWORDRequest) -> SWORDResponse:
        """Retrieve submission metadata."""
        return self.pack(self._get_metadata(*req))

    @response(success=[NO_CONTENT, *REDIRECT],
              must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'MetadataFormat'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress'],
             schema='schema/metadata.json')
    def update_metadata(self, req: SWORDRequest) -> SWORDResponse:
        """Add or update submission metadata."""
        return self.pack(self._update_metadata(*req))

    @property
    def methods(self):
        """HTTP methods supported by this endpoint."""
        return {
            'GET': self.get_metadata,
            'PUT': self.update_metadata,
            'POST': self.update_metadata,
        }


class SWORDContent(SWORDBaseEndpoint):
    """Submission content package, which may contain multiple files."""

    __endpoint__ = 'content'

    @response(success=[OK, *REDIRECT, SEE_OTHER], should=['Packaging'],
              must=[(*REDIRECT, SEE_OTHER, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of', 'Accept-Packaging'])
    def get_content(self, req: SWORDRequest) -> SWORDResponse:
        """Retrieve content as package."""
        return self.pack(self._get_content(*req))

    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type'], should=['Content-Length', 'Digest'],
             may=['Authorization', 'On-Behalf-Of'])
    def add_file(self, req: SWORDRequest) -> SWORDResponse:
        """Add file to submission content."""
        return self.pack(self._add_file(*req))

    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'Packaging'],
             may=['Authorization', 'On-Behalf-Of'])
    def update_content(self, req: SWORDRequest) -> SWORDResponse:
        """Replace submission content."""
        return self.pack(self._update_content(*req))

    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def delete_content(self, req: SWORDRequest) -> SWORDResponse:
        """Delete submission content package."""
        return self.pack(self._delete_content(*req))

    @property
    def methods(self):
        """HTTP methods supported by this endpoint."""
        return {
            'GET': self.get_content,
            'PUT': self.update_content,
            'DELETE': self.delete_content,
            'POST': self.add_file,
        }


class SWORDFile(SWORDBaseEndpoint):
    """Submission content file."""

    __endpoint__ = 'file'

    @response(success=[OK, *REDIRECT, SEE_OTHER],
              must=[(*REDIRECT, SEE_OTHER, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def get_file(self, req: SWORDRequest) -> SWORDResponse:
        """Retrieve individual file from submission."""
        return self.pack(self._get_file(*req))

    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    @request(must=['Content-Type'], should=['Content-Length', 'Digest'],
             may=['Authorization', 'On-Behalf-Of'])
    def update_file(self, req: SWORDRequest) -> SWORDResponse:
        """Replace individual content file."""
        return self.pack(self._update_file(*req))

    @response(success=[NO_CONTENT, *REDIRECT], must=[(*REDIRECT, 'Location')])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def delete_file(self, req: SWORDRequest) -> SWORDResponse:
        """Delete individual content file."""
        return self.pack(self._delete_file(*req))

    @property
    def methods(self):
        """HTTP methods supported by this endpoint."""
        return {
            'GET': self.get_file,
            'PUT': self.update_file,
            'DELETE': self.delete_file
        }


class SWORDCollection(SWORDBaseEndpoint):
    """Repository collection."""

    __endpoint__ = 'collection'

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

    @response(success=[CREATED, ACCEPTED], must=['Location'])
    @request(must=['Content-Type', 'Content-Disposition'],
             should=['Content-Length', 'Digest', 'MetadataFormat',
                     'Packaging'],
             may=['Authorization', 'On-Behalf-Of', 'In-Progress', 'Slug'],
             schema='schema/metadata.json')
    def add_submission(self, req: SWORDRequest) -> SWORDResponse:
        """Deposit new object with metadata, and (optionally) content."""
        return self.pack(self._add_submission(*req))

    @property
    def methods(self):
        """HTTP methods supported by this endpoint."""
        return {'POST': self.add_submission}


class SWORDServiceDocument(SWORDBaseEndpoint):
    """SWORD service document."""

    __endpoint__ = 'service'

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

    @response(success=[OK])
    @request(may=['Authorization', 'On-Behalf-Of'])
    def get_service(self, req: SWORDRequest) -> SWORDResponse:
        """Generate the service document for this submission endpoint."""
        response = self._get_service(*req)
        response[0].update({
            ('sword', 'collections'): self._list_collections(),
            ('sword', 'version'): self.version
        })
        return self.pack(response)

    @property
    def methods(self) -> dict:
        """HTTP methods supported by this endpoint."""
        return {'GET': self.get_service}


def request_wrapper(func):
    """Generate a wrapper that packs request parameters into a SWORDRequest."""
    def pack_request(body: dict, headers: dict, files: dict=None, **extra):
        """Call ``func`` with a SWORDRequest."""
        return func((body, headers, files, extra))
    return pack_request


def interface_factory(controllers: List[type]) -> Callable:
    """Generate a controller factory from a set of controllers."""
    def controller_factory(endpoint: str, method: str) -> Callable:
        """Generate a controller for an API endpoint and method."""
        klass = {kls.__endpoint__: kls for kls in controllers}.get(endpoint)
        if klass is not None:
            return request_wrapper(klass().methods.get(method))
    return controller_factory
