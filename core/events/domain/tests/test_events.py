"""Tests for :class:`.Event`s in :mod:`events.domain.event`."""

from unittest import TestCase, mock
from datetime import datetime
from arxiv import taxonomy
from events import save
from events.domain import event, agent, submission
from events.exceptions import InvalidEvent


class TestSetPrimaryClassification(TestCase):
    """Test :class:`event.SetPrimaryClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now()
        )

    def test_set_primary_with_nonsense(self):
        """Category is not from the arXiv taxonomy."""
        e = event.SetPrimaryClassification(
            creator=self.user,
            submission_id=1,
            category="nonsense"
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".

    def test_set_primary_with_valid_category(self):
        """Category is from the arXiv taxonomy."""
        for category in taxonomy.CATEGORIES.keys():
            e = event.SetPrimaryClassification(
                creator=self.user,
                submission_id=1,
                category=category
            )
            try:
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail("Event should be valid")

    def test_set_primary_already_secondary(self):
        """Category is already set as a secondary."""
        classification = submission.Classification('cond-mat.dis-nn')
        self.submission.secondary_classification.append(classification)
        e = event.SetPrimaryClassification(
            creator=self.user,
            submission_id=1,
            category='cond-mat.dis-nn'
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".


class TestAddSecondaryClassification(TestCase):
    """Test :class:`event.AddSecondaryClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(),
            secondary_classification=[]
        )

    def test_add_secondary_with_nonsense(self):
        """Category is not from the arXiv taxonomy."""
        e = event.AddSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category="nonsense"
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".

    def test_add_secondary_with_valid_category(self):
        """Category is from the arXiv taxonomy."""
        for category in taxonomy.CATEGORIES.keys():
            e = event.AddSecondaryClassification(
                creator=self.user,
                submission_id=1,
                category=category
            )
            try:
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail("Event should be valid")

    def test_add_secondary_already_present(self):
        """Category is already present on the submission."""
        self.submission.secondary_classification.append(
            submission.Classification('cond-mat.dis-nn')
        )
        e = event.AddSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category='cond-mat.dis-nn'
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".

    def test_add_secondary_already_primary(self):
        """Category is already set as primary."""
        classification = submission.Classification('cond-mat.dis-nn')
        self.submission.primary_classification = classification

        e = event.AddSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category='cond-mat.dis-nn'
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".


class TestRemoveSecondaryClassification(TestCase):
    """Test :class:`event.RemoveSecondaryClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(),
            secondary_classification=[]
        )

    def test_add_secondary_with_nonsense(self):
        """Category is not from the arXiv taxonomy."""
        e = event.RemoveSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category="nonsense"
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".

    def test_remove_secondary_with_valid_category(self):
        """Category is from the arXiv taxonomy."""
        classification = submission.Classification('cond-mat.dis-nn')
        self.submission.secondary_classification.append(classification)
        e = event.RemoveSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category='cond-mat.dis-nn'
        )
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail("Event should be valid")

    def test_remove_secondary_not_present(self):
        """Category is not present."""
        e = event.RemoveSecondaryClassification(
            creator=self.user,
            submission_id=1,
            category='cond-mat.dis-nn'
        )
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)    # "Event should not be valid".
