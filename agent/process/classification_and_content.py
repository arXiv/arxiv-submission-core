"""Extract text, and get suggestions, features, and flags from Classifier."""

from typing import Iterable, Optional, Callable, Tuple
from itertools import count
import time
from datetime import datetime
from pytz import UTC

from arxiv.taxonomy import CATEGORIES, Category
from arxiv.integration.api import exceptions

from arxiv.submission import AddClassifierResults, AddContentFlag, AddFeature
from arxiv.submission.domain.flag import Flag, ContentFlag
from arxiv.submission.domain.annotation import Feature
from arxiv.submission.domain.agent import Agent, User
from arxiv.submission.domain.process import ProcessStatus
from arxiv.submission.services import Classifier, PlainTextService
from arxiv.submission.services.plaintext import ExtractionFailed

from .base import Process, step, Retry, Recoverable
from ..domain import Trigger


class PlainTextExtraction(Process):
    """Extract plain text from a compiled PDF."""

    recoverable = (exceptions.BadResponse, exceptions.ConnectionFailed,
                   exceptions.SecurityException)

    def source_id(self, trigger: Trigger) -> int:
        """Get the source ID for the submission content."""
        try:
            return trigger.after.source_content.identifier
        except AttributeError as exc:
            self.fail(exc, 'No source content identifier on post-event state')

    @step(max_retries=None)
    def start_extraction(self, previous: Optional, trigger: Trigger,
                         emit: Callable) -> None:
        """Request extraction by the plain text service."""
        try:
            PlainTextService.request_extraction(self.source_id(trigger))
        except self.recoverable as exc:
            raise Recoverable('Encountered %s; try again' % exc) from exc
        except ExtractionFailed as exc:
            self.fail(exc, 'Extraction service failed to extract text')

    @step(max_retries=None, delay=1, backoff=1, jitter=(0, 1))
    def poll_extraction(self, previous: Optional, trigger: Trigger,
                        emit: Callable) -> None:
        """Poll the plain text service until extraction is complete."""
        source_id = self.source_id(trigger)
        try:
            complete = PlainTextService.extraction_is_complete(source_id)
        except ExtractionFailed as exc:
            self.fail(exc, 'Extraction service failed to extract text')
        except self.recoverable as exc:
            raise Recoverable('Encountered %s; try again' % exc) from exc
        except Exception as exc:
            self.fail(exc, 'Encountered unrecoverable request error')
        if not complete:
            raise Retry('Not complete; try again')

    @step(max_retries=None)
    def retrieve_content(self, previous: Optional, trigger: Trigger,
                         emit: Callable) -> bytes:
        """Retrieve the extracted plain text."""
        source_id = self.source_id(trigger)
        try:
            return PlainTextService.retrieve_content(source_id)
        except self.recoverable as exc:
            raise Recoverable('Encountered %s; try again' % exc) from exc
        except Exception as exc:
            self.fail(exc, 'Encountered unrecoverable request error')


class RunAutoclassifier(PlainTextExtraction):
    """
    Extract plain text and poll the autoclassifier.

    In addition to generating classification suggestions, the current
    implementation of the autoclassifier also generates features (like word
    counts) and content flags (e.g. possible language issues, line numbers).
    """

    CLASSIFIER_FLAGS = {
        '%stop': None,  # We will handle this ourselves.
        'stops': None,  # We will handle this ourselves.
        'language': ContentFlag.Type.LANGUAGE,
        'charset': ContentFlag.Type.CHARACTER_SET,
        'linenos': ContentFlag.Type.LINE_NUMBERS
    }

    @step(max_retries=None)
    def call_classifier(self, content: bytes, trigger: Trigger,
                        emit: Callable) -> None:
        """Send plain text content to the autoclassifier."""
        try:
            # The autoclassifier runs synchronously; it's pretty fast.
            self.process_result(Classifier.classify(content), trigger, emit)
        except self.recoverable as exc:
            raise Recoverable('Encountered %s; try again' % exc) from exc
        except Exception as exc:
            self.fail(exc, 'Encountered unrecoverable request error')

    def process_result(self, result: Tuple, trigger: Trigger,
                       emit: Callable) -> None:
        """Process the results returned by the autoclassifier."""
        suggestions, flags, counts = result
        results = [{'category': suggestion.category,
                   'probability': suggestion.probability}
                   for suggestion in suggestions]
        emit(AddClassifierResults(creator=trigger.creator, results=results))

        for flag in flags:
            now = datetime.now(UTC).isoformat()
            comment = "flag from classification succeeded at %s" % now
            flag_type = self.CLASSIFIER_FLAGS.get(flag.key)
            if flag_type is None:
                continue
            emit(AddContentFlag(creator=self.agent, flag_type=flag_type,
                                flag_data=flag.value, comment=comment))

        emit(AddFeature(creator=self.agent,
                        feature_type=Feature.Type.CHARACTER_COUNT,
                        feature_value=counts.chars))
        emit(AddFeature(creator=self.agent,
                        feature_type=Feature.Type.PAGE_COUNT,
                        feature_value=counts.pages))
        emit(AddFeature(creator=self.agent,
                        feature_type=Feature.Type.STOPWORD_COUNT,
                        feature_value=counts.stops))
        emit(AddFeature(creator=self.agent,
                        feature_type=Feature.Type.WORD_COUNT,
                        feature_value=counts.words))
        emit(AddFeature(creator=self.agent,
                        feature_type=Feature.Type.STOPWORD_PERCENT,
                        feature_value=counts.stops/counts.words))


class CheckStopwordPercent(Process):
    """Check the submission content for too low percentage of stopwords."""

    @step()
    def check_stop_percent(self, content: bytes, trigger: Trigger,
                           emit: Callable) -> None:
        """Flag the submission if the percentage of stopwords is too low."""
        feats = [feature for feature in trigger.after.features.values()
                 if feature.feature_type is Feature.Type.STOPWORD_PERCENT]
        if not feats:
            self.fail(message='No stopword percentage feature on submission')

        # TODO: we are assuming that there is only one. Is that ever not true?
        if feats[0].feature_value < trigger.params['LOW_STOP_PERCENT']:
            comment = "Classifier reports low stops or %stops"
            emit(AddContentFlag(creator=self.agent,
                                flag_type=ContentFlag.Type.LOW_STOP_PERCENT,
                                flag_data=trigger.event.feature_value,
                                comment=comment))


class CheckStopwordCount(Process):
    """Check the submission content for too low stopword count."""

    @step()
    def check_stop_count(self, content: bytes, trigger: Trigger,
                         emit: Callable) -> None:
        """Flag the submission if the number of stopwords is too low."""
        feats = [feature for feature in trigger.after.features.values()
                 if feature.feature_type is Feature.Type.STOPWORD_COUNT]
        if not feats:
            self.fail(message='No stopword percentage feature on submission')

        # TODO: we are assuming that there is only one. Is that ever not true?
        if feats[0].feature_value < trigger.params['LOW_STOP']:
            emit(AddContentFlag(
                creator=self.agent,
                flag_type=ContentFlag.Type.LOW_STOP,
                flag_data=trigger.event.feature_value,
                comment="Classifier reports low stops or %stops"
            ))
