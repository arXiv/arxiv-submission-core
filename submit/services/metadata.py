"""Integration with reference metadata store."""

import os
import boto3
from boto3.dynamodb.conditions import Key
from botodomain.exceptions import ClientError
import logging
from submit.context import get_application_config, get_application_global


logger = logging.getLogger(__name__)


class MetadataSession(object):
    """Container for datastore sessions."""

    def __init__(self, endpoint_url: str, aws_access_key: str,
                 aws_secret_key: str, aws_session_token: str, region_name: str,
                 verify: bool=True, table_name: str='Submission') -> None:
        """Initialize datastore sessions."""
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', verify=verify,
                                       region_name=region_name,
                                       endpoint_url=endpoint_url,
                                       aws_access_key_id=aws_access_key,
                                       aws_secret_access_key=aws_secret_key,
                                       aws_session_token=aws_session_token)
        self.table = self.dynamodb.Table(self.table_name)

    def create_table(self) -> None:
        """Set up a new table in DynamoDB. Blocks until table is available."""
        try:
            table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {'AttributeName': 'id',
                     'KeyType': 'HASH'},
                    {'AttributeName': 'created', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {"AttributeName": 'id', "AttributeType": "S"},
                    {"AttributeName": 'status', "AttributeType": "S"},
                    {"AttributeName": 'created', "AttributeType": "S"}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'StatusIndex',
                        'KeySchema': [
                            {'AttributeName': 'status', 'KeyType': 'HASH'}
                        ],
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 5,
                            'WriteCapacityUnits': 5
                        },
                        'Projection': {
                            "ProjectionType": 'ALL'
                        }
                    },
                ],
                ProvisionedThroughput={
                    'ReadCapacityUnits': 5,
                    'WriteCapacityUnits': 5
                }
            )
            waiter = table.meta.client.get_waiter('table_exists')
            waiter.wait(TableName=self.table_name)
        except ClientError:
            logger.debug('Table exists: %s', self.table_name)


def init_app(app: object) -> None:
    """
    Set default configuration parameters on an application.

    Parameters
    ----------
    app : :class:`flask.Flask`
    """
    config = get_application_config(app)
    config.setdefault('DYNAMODB_ENDPOINT',
                      'https://dynamodb.us-east-1.amazonaws.com')
    config.setdefault('AWS_REGION', 'us-east-1')
    config.setdefault('DYNAMODB_VERIFY', 'true')
    config.setdefault('METADATA_TABLE_NAME', 'Submission')


def get_session(app: object=None) -> MetadataSession:
    """
    Initialize a session with the data store.

    Parameters
    ----------
    app : :class:`flask.Flask`
        If not provided, will attempt to get the current application.

    Returns
    -------
    :class:`.DataStoreSession`
    """
    config = get_application_config(app)
    access_key = config.get('AWS_ACCESS_KEY_ID', None)
    secret_key = config.get('AWS_SECRET_ACCESS_KEY', None)
    token = config.get('AWS_SESSION_TOKEN', None)
    if not access_key or not secret_key:
        raise RuntimeError('Could not find usable credentials')
    endpoint_url = config.get('DYNAMODB_ENDPOINT', None)
    region_name = config.get('AWS_REGION', 'us-east-1')
    table_name = config.get('METADATA_TABLE_NAME')
    verify = config.get('DYNAMODB_VERIFY', 'true') == 'true'
    return MetadataSession(endpoint_url, access_key, secret_key, token,
                           region_name, verify=verify, table_name=table_name)


def current_session():
    """Get/create :class:`.ReferenceStoreSession` for this context."""
    g = get_application_global()
    if g is None:
        return get_session()
    if 'metadata' not in g:
        g.metadata = get_session()
    return g.metadata


def store_references(*args, **kwargs):
    """
    Store extracted references for a document.

    See :meth:`.references.ReferenceStoreSession.create`.
    """
    return current_session().references.create(*args, **kwargs)


def get_reference(*args, **kwargs):
    """
    Retrieve metadata for a specific reference in a document.

    See :meth:`.references.ReferenceStoreSession.retrieve`.
    """
    return current_session().references.retrieve(*args, **kwargs)


def get_latest_extraction(*args, **kwargs):
    """
    Retrieve info about the most recent extraction for a document.

    See :meth:`.extraction.ExtractionSession.latest`.
    """
    return current_session().extractions.latest(*args, **kwargs)


def get_latest_extractions(*args, **kwargs):
    """
    Retrieve the most recent extracted references for a document.

    See :meth:`.references.ReferenceStoreSession.retrieve_latest`.
    """
    return current_session().references.retrieve_latest(*args, **kwargs)


def store_raw_extraction(*args, **kwargs):
    """
    Store raw extraction metadata for a single extractor.

    See :meth:`.raw.RawExtractionSession.store_extraction`.
    """
    return current_session().raw.store_extraction(*args, **kwargs)


def get_raw_extraction(*args, **kwargs):
    """
    Retrieve raw extraction metadata for a single extractor.

    See :meth:`.raw.RawExtractionSession.get_extraction`.
    """
    return current_session().raw.get_extraction(*args, **kwargs)


def init_db():
    """Create datastore tables."""
    session = current_session()
    session.create_table()
