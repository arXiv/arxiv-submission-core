"""Quality control checks that are performed after submission."""

from unittest import TestCase, mock
import tempfile

from flask import Flask

from ...services import classic, plaintext, classifier
from ... import save, load, load_fast, domain, exceptions, tasks, core, rules
from ...rules.tests.data.titles import TITLES
from ...rules import classification_and_content


CCO = 'http://creativecommons.org/publicdomain/zero/1.0/'
TEX = domain.submission.SubmissionContent.Format('tex')


class TestPostSubmissionChecks(TestCase):
    """
    Submitter creates, completes, and finalizes a new submission.

    At this point the submission is in the queue for moderation and
    announcement.
    """

    @classmethod
    def setUpClass(cls):
        """Instantiate an app for use with a SQLite database."""
        _, db = tempfile.mkstemp(suffix='.sqlite')
        cls.app = Flask('foo')
        cls.app.config['CLASSIC_DATABASE_URI'] = f'sqlite:///{db}'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

        with cls.app.app_context():
            classic.init_app(cls.app)

    def setUp(self):
        """Set up the database."""
        with self.app.app_context():
            classic.create_all()

            session = classic.current_session()
            for ident, title, creator in TITLES:
                session.add(classic.models.Submission(
                    status=classic.models.Submission.SUBMITTED,
                    title=title,
                    submitter_id=creator.native_id,
                    submitter_email=creator.email
                ))
            session.commit()

    @mock.patch(f'{tasks.__name__}.get_application_config',
                mock.MagicMock(return_value={'ENABLE_ASYNC': 0}))
    @mock.patch(f'{domain.__name__}.event.event.get_application_config',
                mock.MagicMock(return_value={'ENABLE_CALLBACKS': 1}))
    @mock.patch(f'{classifier.__name__}.Classifier.classify')
    @mock.patch(f'{classification_and_content.__name__}.PlainTextService')
    def test_submission(self, mock_plaintext, mock_classify):
        """Create, and complete the submission."""
        mock_plaintext.request_extraction.return_value = None
        mock_plaintext.extraction_is_complete.return_value = True
        mock_plaintext.retrieve_content.return_value = b'foo content'
        mock_classify.return_value = (
            [classifier.classifier.Suggestion('cs.DL', 0.9),
             classifier.classifier.Suggestion('cs.AI', 0.4)],
            [classifier.classifier.Flag('%stop', '0.001'),
             classifier.classifier.Flag('linenos', '1')],
            classifier.classifier.Counts(32345, 43, 1, 1000)
        )

        self.submitter = domain.agent.User(1234, email='j.user@somewhere.edu',
                                           forename='Jane', surname='User',
                                           endorsements=['cs.AI', 'cs.IR'])
        self.defaults = {'creator': self.submitter}
        with self.app.app_context():
            title = 'a lepton qed of colliders or interactions with strong' \
                    ' field electron laser'
            self.doi = "10.01234/56789"
            submission, self.events = save(
                domain.event.CreateSubmission(**self.defaults),
                domain.event.ConfirmContactInformation(**self.defaults),
                domain.event.ConfirmAuthorship(**self.defaults),
                domain.event.ConfirmPolicy(**self.defaults),
                domain.event.SetTitle(title=title, **self.defaults),
                domain.event.SetLicense(license_uri=CCO,
                                        license_name="CC0 1.0",
                                        **self.defaults),
                domain.event.SetPrimaryClassification(category="cs.AI",
                                                      **self.defaults),
                domain.event.SetUploadPackage(checksum="a9s9k342900ks03330029",
                                              source_format=TEX,
                                              identifier=123,
                                              uncompressed_size=593992,
                                              compressed_size=593992,
                                              **self.defaults),
                domain.event.SetAbstract(abstract="Very abstract " * 20,
                                         **self.defaults),
                domain.event.SetComments(comments="Fine indeed " * 10,
                                         **self.defaults),
                domain.event.SetJournalReference(journal_ref="Foo 1992",
                                                 **self.defaults),
                domain.event.SetDOI(doi=self.doi, **self.defaults),
                domain.event.SetAuthors(authors_display='Robert Paulson (FC)',
                                        **self.defaults),
                domain.event.ConfirmPreview(**self.defaults),
                domain.event.FinalizeSubmission(**self.defaults)
            )

        # Check for proposal based on classifier results.
        proposals = list(submission.proposals.values())
        self.assertEqual(proposals[0].proposed_event_data['category'], 'cs.DL')

        # Check for content flags based on classifier results.
        flag_types = [flag.flag_type for flag in submission.flags.values()]
        self.assertIn(domain.flag.ContentFlag.FlagTypes.LINE_NUMBERS,
                      flag_types)
        self.assertIn(domain.flag.ContentFlag.FlagTypes.LOW_STOP_PERCENT,
                      flag_types)
        self.assertIn(domain.flag.ContentFlag.FlagTypes.LOW_STOP,
                      flag_types)

        # Check for flags based on duplicate title checks.
        self.assertIn(
            domain.flag.MetadataFlag.FlagTypes.POSSIBLE_DUPLICATE_TITLE,
            flag_types
        )

        # Check for features returned by the classifier.
        feature_types = [feature.feature_type
                         for feature in submission.features.values()]
        self.assertIn(domain.annotation.Feature.FeatureTypes.WORD_COUNT,
                      feature_types)
        self.assertIn(domain.annotation.Feature.FeatureTypes.STOPWORD_COUNT,
                      feature_types)
        self.assertIn(domain.annotation.Feature.FeatureTypes.STOPWORD_PERCENT,
                      feature_types)
        self.assertIn(domain.annotation.Feature.FeatureTypes.CHARACTER_COUNT,
                      feature_types)
        self.assertIn(domain.annotation.Feature.FeatureTypes.PAGE_COUNT,
                      feature_types)

        # Check the classic database.
        with self.app.app_context():
            session = classic.current_session()

            # Verify that the reclassification proposal is created.
            proposals = session.query(classic.models.CategoryProposal).all()
            self.assertEqual(len(proposals), 1)

            # Verify that the admin log is updated.
            logs = session.query(classic.models.AdminLogEntry).all()
            messages = [log.logtext for log in logs]
            self.assertIn('Classifier reports low stops or %stops',
                          messages)
            self.assertIn('selected primary cs.AI has probability 0.4',
                          messages)
            programs = [log.program for log in logs]
            self.assertIn(f'AddClassifierResults::{rules.__name__}.reclassification.propose', programs)
            self.assertIn(f'AddFeature::{rules.__name__}.classification_and_content.check_stop_count', programs)
            commands = [log.command for log in logs]
            self.assertIn('admin comment', commands)

    def tearDown(self):
        """Clear the database after each test."""
        with self.app.app_context():
            classic.drop_all()
