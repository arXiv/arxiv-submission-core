"""Implements the Kinesis stream consumer for the submission agent."""

import json
import os
import time
from typing import List, Any, Optional, Dict

from flask import Flask
from retry import retry

from botocore.exceptions import WaiterError, NoCredentialsError, \
    PartialCredentialsError, BotoCoreError, ClientError

from arxiv.base import logging
from arxiv.integration.kinesis import consumer
from arxiv.submission.serializer import loads
from arxiv.submission.domain.submission import Submission
from arxiv.submission.domain.event import Event, AddProcessStatus

from . import rules
from .services import database
from .factory import create_app

logger = logging.getLogger(__name__)
logger.propagate = False


class SubmissionEventConsumer(consumer.BaseConsumer):
    """Consumes submission events, and spawns processes based on rules."""

    def process_record(self, record: dict) -> None:
        """
        Evaluate an event against registered rules.

        Parameters
        ----------
        data : bytes
        partition_key : bytes
        sequence_number : int
        sub_sequence_number : int

        """
        logger.info(f'Processing record %s', record["SequenceNumber"])
        try:
            data = loads(record['Data'].decode('utf-8'))
        except json.decoder.JSONDecodeError as exc:
            logger.error("Error (%s) while deserializing from data %s",
                         exc, record['Data'])
            raise exc

        if type(data['event']) is AddProcessStatus:
            logger.debug('Storing event %s', data['event'])
            self._store_event(data['event'])
            logger.debug('..stored.')
        logger.debug('Evaluating event %s', data['event'].event_id)
        self._evaluate(data['event'], data['before'], data['after'])
        logger.debug('Done processing record %s', record["SequenceNumber"])

    @retry(backoff=2, jitter=(0, 1), logger=logger)
    def _store_event(self, event: AddProcessStatus) -> None:
        database.store_event(event)

    @retry(backoff=2, jitter=(0, 1), logger=logger)
    def _evaluate(self, event: Event, before: Submission,
                  after: Submission) -> None:
        rules.evaluate(event, before, after)

    def wait_for_stream(self) -> None:
        """
        Wait for the stream to become available.

        If the stream becomes available, returns ``None``. Otherwise, raises
        a :class:`.StreamNotAvailable` exception.

        Raises
        ------
        :class:`.StreamNotAvailable`
            Raised when the stream could not be reached.

        """
        waiter = self.client.get_waiter('stream_exists')
        try:
            logger.error(f'Waiting for stream {self.stream_name}')
            waiter.wait(
                StreamName=self.stream_name,
                Limit=1,
                ExclusiveStartShardId=self.shard_id
            )
        except WaiterError as e:
            logger.error('Failed to get stream while waiting')
            raise consumer.exceptions.StreamNotAvailable('Could not connect to stream') from e
        except (PartialCredentialsError, NoCredentialsError) as e:
            logger.error('Credentials missing or incomplete: %s', e.msg)
            raise consumer.exceptions.ConfigurationError('Credentials missing') from e
        logger.debug('Done waiting')

    def go(self) -> None:
        logger.debug('Go!')
        super(SubmissionEventConsumer, self).go()


class DatabaseCheckpointManager:
    """
    Provides database-backed loading and updating of consumer checkpoints.
    """

    def __init__(self, shard_id: str) -> None:
        """Get the last checkpoint."""
        self.shard_id = shard_id
        self.position = database.get_latest_position(self.shard_id)

    def checkpoint(self, position: str) -> None:
        """Checkpoint at ``position``."""
        try:
            database.store_position(position, self.shard_id)
            self.position = position
        except Exception as e:
            raise consumer.CheckpointError('Could not checkpoint') from e


def process_stream(app: Flask, duration: Optional[int] = None) -> None:
    """
    Configure and run the record processor.

    Parameters
    ----------
    duration : int
        Time (in seconds) to run record processing. If None (default), will
        run "forever".

    """
    # We use the Flask application instance for configuration, and to manage
    # integrations with metadata service, search index.
    checkpointer = DatabaseCheckpointManager(app.config['KINESIS_SHARD_ID'])
    consumer.process_stream(SubmissionEventConsumer, app.config,
                            checkpointmanager=checkpointer, duration=duration)


def start_agent() -> None:
    """Start the record processor."""
    app = create_app()
    with app.app_context():
        database.await_connection()
        if not database.tables_exist():
            database.create_all()
        process_stream(app)


if __name__ == '__main__':
    start_agent()
