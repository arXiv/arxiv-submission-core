from typing import Optional

import boto3

from arxiv.integration.meta import MetaIntegration
from arxiv.base.globals import get_application_config, get_application_global

from ...domain import Submission, Event
from ...serializer import dumps


class StreamPublisher(metaclass=MetaIntegration):
    def __init__(self, stream: str, partition_key: str,
                 aws_access_key_id: str, aws_secret_access_key: str,
                 region_name: str, endpoint_url: Optional[str] = None,
                 verify: bool = True) -> None:
        self.stream = stream
        self.partition_key = partition_key
        self.client = boto3.client('kinesis',
                                   region_name=region_name,
                                   endpoint_url=endpoint_url,
                                   aws_access_key_id=aws_access_key_id,
                                   aws_secret_access_key=aws_secret_access_key,
                                   verify=verify)

    @classmethod
    def init_app(cls, app: object = None) -> None:
        """Set default configuration params for an application instance."""
        config = get_application_config(app)
        config.setdefault('AWS_ACCESS_KEY_ID', '')
        config.setdefault('AWS_SECRET_ACCESS_KEY', '')
        config.setdefault('AWS_REGION', 'us-east-1')
        config.setdefault('KINESIS_ENDPOINT', None)
        config.setdefault('KINESIS_VERIFY', True)
        config.setdefault('KINESIS_STREAM', 'SubmissionEvents')
        config.setdefault('KINESIS_PARTITION_KEY', '0')

    @classmethod
    def get_session(cls, app: object = None) -> 'StreamPublisher':
        """Get a new session with the stream."""
        config = get_application_config(app)
        aws_access_key_id = config['AWS_ACCESS_KEY_ID']
        aws_secret_access_key = config['AWS_SECRET_ACCESS_KEY']
        aws_region = config['AWS_REGION']
        kinesis_endpoint = config['KINESIS_ENDPOINT']
        kinesis_verify = config['KINESIS_VERIFY']
        kinesis_stream = config['KINESIS_STREAM']
        partition_key = config['KINESIS_PARTITION_KEY']
        return cls(kinesis_stream, partition_key, aws_access_key_id,
                   aws_secret_access_key, aws_region, kinesis_endpoint,
                   kinesis_verify)

    @classmethod
    def current_session(cls) -> 'StreamPublisher':
        """Get/create :class:`.StreamPublisher` for this context."""
        g = get_application_global()
        if not g:
            return cls.get_session()
        elif 'stream' not in g:
            g.stream = cls.get_session()   # type: ignore
        return g.stream    # type: ignore

    def put(self, event: Event, before: Submission, after: Submission) -> None:
        """Put an :class:`.Event` on the stream."""
        payload = {'event': event, 'before': before, 'after': after}
        data = bytes(dumps(payload), encoding='utf-8')
        self.client.put_record(StreamName=self.stream, Data=data,
                               PartitionKey=self.partition_key)
