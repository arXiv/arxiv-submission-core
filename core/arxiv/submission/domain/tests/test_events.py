"""Tests for :class:`.Event` instances in :mod:`arxiv.submission.domain.event`."""

from unittest import TestCase, mock
from datetime import datetime
from pytz import UTC
from mimesis import Text

from arxiv import taxonomy
from ... import save
from .. import event, agent, submission, meta
from ...exceptions import InvalidEvent


class TestWithdrawalSubmission(TestCase):
    """Test :class:`event.RequestWithdrawal`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(
            12345,
            'uuser@cornell.edu',
            endorsements=[meta.Classification('astro-ph.GA'),
                          meta.Classification('astro-ph.CO')]
        )
        self.submission = submission.Submission(
            submission_id=1,
            status=submission.Submission.ANNOUNCED,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC),
            source_content=submission.SubmissionContent(
                identifier='6543',
                source_format=submission.SubmissionContent.Format('pdf'),
                checksum='asdf2345',
                uncompressed_size=594930,
                compressed_size=594930
            ),
            primary_classification=meta.Classification('astro-ph.GA'),
            secondary_classification=[meta.Classification('astro-ph.CO')],
            license=meta.License(uri='http://free', name='free'),
            arxiv_id='1901.001234',
            version=1,
            submitter_contact_verified=True,
            submitter_is_author=True,
            submitter_accepts_policy=True,
            submitter_confirmed_preview=True,
            metadata=submission.SubmissionMetadata(
                title='the best title',
                abstract='very abstract',
                authors_display='J K Jones, F W Englund',
                doi='10.1000/182',
                comments='These are the comments'
            )
        )

    def test_request_withdrawal(self):
        """Request that a paper be withdrawn."""
        e = event.RequestWithdrawal(creator=self.user, reason="no good")
        e.validate(self.submission)
        replacement = e.apply(self.submission)
        self.assertEqual(replacement.arxiv_id, self.submission.arxiv_id)
        self.assertEqual(replacement.version, self.submission.version)
        self.assertEqual(replacement.status,
                         submission.Submission.ANNOUNCED)
        self.assertTrue(replacement.has_active_requests)
        self.assertTrue(self.submission.is_announced)
        self.assertTrue(replacement.is_announced)

    def test_request_without_a_reason(self):
        """A reason is required."""
        e = event.RequestWithdrawal(creator=self.user)
        with self.assertRaises(event.InvalidEvent):
            e.validate(self.submission)

    def test_request_without_announced_submission(self):
        """The submission must already be announced."""
        e = event.RequestWithdrawal(creator=self.user, reason="no good")
        with self.assertRaises(event.InvalidEvent):
            e.validate(mock.MagicMock(announced=False))


class TestReplacementSubmission(TestCase):
    """Test :class:`event.CreateSubmission` with a replacement."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(
            12345,
            'uuser@cornell.edu',
            endorsements=[meta.Classification('astro-ph.GA'),
                          meta.Classification('astro-ph.CO')]
        )
        self.submission = submission.Submission(
            submission_id=1,
            status=submission.Submission.ANNOUNCED,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC),
            source_content=submission.SubmissionContent(
                identifier='6543',
                source_format=submission.SubmissionContent.Format('pdf'),
                checksum='asdf2345',
                uncompressed_size=594930,
                compressed_size=594930
            ),
            primary_classification=meta.Classification('astro-ph.GA'),
            secondary_classification=[meta.Classification('astro-ph.CO')],
            license=meta.License(uri='http://free', name='free'),
            arxiv_id='1901.001234',
            version=1,
            submitter_contact_verified=True,
            submitter_is_author=True,
            submitter_accepts_policy=True,
            submitter_confirmed_preview=True,
            metadata=submission.SubmissionMetadata(
                title='the best title',
                abstract='very abstract',
                authors_display='J K Jones, F W Englund',
                doi='10.1000/182',
                comments='These are the comments'
            )
        )

    def test_create_submission_replacement(self):
        """A replacement is a new submission based on an old submission."""
        e = event.CreateSubmissionVersion(creator=self.user)
        replacement = e.apply(self.submission)
        self.assertEqual(replacement.arxiv_id, self.submission.arxiv_id)
        self.assertEqual(replacement.version, self.submission.version + 1)
        self.assertEqual(replacement.status, submission.Submission.WORKING)
        self.assertTrue(self.submission.is_announced)
        self.assertFalse(replacement.is_announced)

        self.assertIsNone(replacement.source_content)

        # The user is asked to reaffirm these points.
        self.assertFalse(replacement.submitter_contact_verified)
        self.assertFalse(replacement.submitter_accepts_policy)
        self.assertFalse(replacement.submitter_confirmed_preview)
        self.assertFalse(replacement.submitter_contact_verified)

        # These should all stay the same.
        self.assertEqual(replacement.metadata.title,
                         self.submission.metadata.title)
        self.assertEqual(replacement.metadata.abstract,
                         self.submission.metadata.abstract)
        self.assertEqual(replacement.metadata.authors,
                         self.submission.metadata.authors)
        self.assertEqual(replacement.metadata.authors_display,
                         self.submission.metadata.authors_display)
        self.assertEqual(replacement.metadata.msc_class,
                         self.submission.metadata.msc_class)
        self.assertEqual(replacement.metadata.acm_class,
                         self.submission.metadata.acm_class)
        self.assertEqual(replacement.metadata.doi,
                         self.submission.metadata.doi)
        self.assertEqual(replacement.metadata.journal_ref,
                         self.submission.metadata.journal_ref)


class TestDOIorJREFAfterAnnounce(TestCase):
    """Test :class:`event.SetDOI` or :class:`event.SetJournalReference`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(
            12345,
            'uuser@cornell.edu',
            endorsements=[meta.Classification('astro-ph.GA'),
                          meta.Classification('astro-ph.CO')]
        )
        self.submission = submission.Submission(
            submission_id=1,
            status=submission.Submission.ANNOUNCED,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC),
            source_content=submission.SubmissionContent(
                identifier='6543',
                source_format=submission.SubmissionContent.Format('pdf'),
                checksum='asdf2345',
                uncompressed_size=594930,
                compressed_size=594930
            ),
            primary_classification=meta.Classification('astro-ph.GA'),
            secondary_classification=[meta.Classification('astro-ph.CO')],
            license=meta.License(uri='http://free', name='free'),
            arxiv_id='1901.001234',
            version=1,
            submitter_contact_verified=True,
            submitter_is_author=True,
            submitter_accepts_policy=True,
            submitter_confirmed_preview=True,
            metadata=submission.SubmissionMetadata(
                title='the best title',
                abstract='very abstract',
                authors_display='J K Jones, F W Englund',
                doi='10.1000/182',
                comments='These are the comments'
            )
        )

    def test_create_submission_jref(self):
        """A JREF is just like a replacement, but different."""
        e = event.SetDOI(creator=self.user, doi='10.1000/182')
        after = e.apply(self.submission)
        self.assertEqual(after.arxiv_id, self.submission.arxiv_id)
        self.assertEqual(after.version, self.submission.version)
        self.assertEqual(after.status, submission.Submission.ANNOUNCED)
        self.assertTrue(self.submission.is_announced)
        self.assertTrue(after.is_announced)

        self.assertIsNotNone(after.submission_id)
        self.assertEqual(self.submission.submission_id, after.submission_id)

        # The user is NOT asked to reaffirm these points.
        self.assertTrue(after.submitter_contact_verified)
        self.assertTrue(after.submitter_accepts_policy)
        self.assertTrue(after.submitter_confirmed_preview)
        self.assertTrue(after.submitter_contact_verified)

        # These should all stay the same.
        self.assertEqual(after.metadata.title,
                         self.submission.metadata.title)
        self.assertEqual(after.metadata.abstract,
                         self.submission.metadata.abstract)
        self.assertEqual(after.metadata.authors,
                         self.submission.metadata.authors)
        self.assertEqual(after.metadata.authors_display,
                         self.submission.metadata.authors_display)
        self.assertEqual(after.metadata.msc_class,
                         self.submission.metadata.msc_class)
        self.assertEqual(after.metadata.acm_class,
                         self.submission.metadata.acm_class)
        self.assertEqual(after.metadata.doi,
                         self.submission.metadata.doi)
        self.assertEqual(after.metadata.journal_ref,
                         self.submission.metadata.journal_ref)



class TestSetPrimaryClassification(TestCase):
    """Test :class:`event.SetPrimaryClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(
            12345,
            'uuser@cornell.edu',
            endorsements=[meta.Classification('astro-ph.GA'),
                          meta.Classification('astro-ph.CO')]
        )
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
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
            if category in self.user.endorsements:
                try:
                    e.validate(self.submission)
                except InvalidEvent as e:
                    self.fail("Event should be valid")
            else:
                with self.assertRaises(InvalidEvent):
                    e.validate(self.submission)

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
            created=datetime.now(UTC),
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
        for category in taxonomy.CATEGORIES_ACTIVE.keys():
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
            created=datetime.now(UTC),
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


class TestSetAuthors(TestCase):
    """Test :class:`event.SetAuthors`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_canonical_authors_provided(self):
        """Data includes canonical author display string."""
        e = event.SetAuthors(creator=self.user,
                                submission_id=1,
                                authors=[submission.Author()],
                                authors_display="Foo authors")
        try:
            e.validate(self.submission)
        except Exception as e:
            self.fail(str(e), "Data should be valid")
        s = e.project(self.submission)
        self.assertEqual(s.metadata.authors_display, e.authors_display,
                         "Authors string should be updated")

    def test_canonical_authors_not_provided(self):
        """Data does not include canonical author display string."""
        e = event.SetAuthors(
            creator=self.user,
            submission_id=1,
            authors=[
                submission.Author(
                    forename="Bob",
                    surname="Paulson",
                    affiliation="FSU"
                )
            ])
        self.assertEqual(e.authors_display, "Bob Paulson (FSU)",
                         "Display string should be generated automagically")

        try:
            e.validate(self.submission)
        except Exception as e:
            self.fail(str(e), "Data should be valid")
        s = e.project(self.submission)
        self.assertEqual(s.metadata.authors_display, e.authors_display,
                         "Authors string should be updated")

    def test_canonical_authors_contains_et_al(self):
        """Author display value contains et al."""
        e = event.SetAuthors(creator=self.user,
                                submission_id=1,
                                authors=[submission.Author()],
                                authors_display="Foo authors, et al")
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)


class TestSetTitle(TestCase):
    """Tests for :class:`.event.SetTitle`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_empty_value(self):
        """Title is set to an empty string."""
        e = event.SetTitle(creator=self.user, title='')
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)

    def test_reasonable_title(self):
        """Title is set to some reasonable value smaller than 240 chars."""
        for _ in range(100):    # Add a little fuzz to the mix.
            for locale in LOCALES:
                title = Text(locale=locale).text(6)[:240] \
                    .strip() \
                    .rstrip('.') \
                    .replace('@', '') \
                    .replace('#', '') \
                    .title()
                e = event.SetTitle(creator=self.user, title=title)
                try:
                    e.validate(self.submission)
                except InvalidEvent as e:
                    self.fail('Failed to handle title: %s' % title)

    def test_all_caps_title(self):
        """Title is all uppercase."""
        title = Text().title()[:240].upper()
        e = event.SetTitle(creator=self.user, title=title)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)

    def test_title_ends_with_period(self):
        """Title ends with a period."""
        title = Text().title()[:239] + "."
        e = event.SetTitle(creator=self.user, title=title)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)

    def test_title_ends_with_ellipsis(self):
        """Title ends with an ellipsis."""
        title = Text().title()[:236] + "..."
        e = event.SetTitle(creator=self.user, title=title)
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail("Should accept ellipsis")

    def test_huge_title(self):
        """Title is set to something unreasonably large."""
        title = Text().text(200)    # 200 sentences.
        e = event.SetTitle(creator=self.user, title=title)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)

    def test_title_with_html_escapes(self):
        """Title should not allow HTML escapes."""
        e = event.SetTitle(creator=self.user, title='foo &nbsp; title')
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)


class TestSetAbstract(TestCase):
    """Tests for :class:`.event.SetAbstract`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_empty_value(self):
        """Abstract is set to an empty string."""
        e = event.SetAbstract(creator=self.user, abstract='')
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)

    def test_reasonable_abstract(self):
        """Abstract is set to some reasonable value smaller than 1920 chars."""
        for locale in LOCALES:
            abstract = Text(locale=locale).text(20)[:1920]
            e = event.SetAbstract(creator=self.user, abstract=abstract)
            try:
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle abstract: %s' % abstract)

    def test_huge_abstract(self):
        """Abstract is set to something unreasonably large."""
        abstract = Text().text(200)    # 200 sentences.
        e = event.SetAbstract(creator=self.user, abstract=abstract)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)


class TestSetDOI(TestCase):
    """Tests for :class:`.event.SetDOI`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_empty_doi(self):
        """DOI is set to an empty string."""
        doi = ""
        e = event.SetDOI(creator=self.user, doi=doi)
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail('Failed to handle valid DOI: %s' % e)

    def test_valid_doi(self):
        """DOI is set to a single valid DOI."""
        doi = "10.1016/S0550-3213(01)00405-9"
        e = event.SetDOI(creator=self.user, doi=doi)
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail('Failed to handle valid DOI: %s' % e)

    def test_multiple_valid_dois(self):
        """DOI is set to multiple valid DOIs."""
        doi = "10.1016/S0550-3213(01)00405-9, 10.1016/S0550-3213(01)00405-8"
        e = event.SetDOI(creator=self.user, doi=doi)
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail('Failed to handle valid DOI: %s' % e)

    def test_invalid_doi(self):
        """DOI is set to something other than a valid DOI."""
        not_a_doi = "101016S0550-3213(01)00405-9"
        e = event.SetDOI(creator=self.user, doi=not_a_doi)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)


class TestSetReportNumber(TestCase):
    """Tests for :class:`.event.SetReportNumber`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_valid_report_number(self):
        """Valid report number values are used."""
        values = [
            "IPhT-T10/027",
            "SITP 10/04, OIQP-10-01",
            "UK/09-07",
            "COLO-HEP-550, UCI-TR-2009-12",
            "TKYNT-10-01, UTHEP-605",
            "1003.1130",
            "CDMTCS-379",
            "BU-HEPP-09-06",
            "IMSC-PHYSICS/08-2009, CU-PHYSICS/2-2010",
            "CRM preprint No. 867",
            "SLAC-PUB-13848, AEI-2009-110, ITP-UH-18/09",
            "SLAC-PUB-14011",
            "KUNS-2257, DCPT-10/11",
            "TTP09-41, SFB/CPP-09-110, Alberta Thy 16-09",
            "DPUR/TH/20",
            "KEK Preprint 2009-41, Belle Preprint 2010-02, NTLP Preprint 2010-01",
            "CERN-PH-EP/2009-018",
            "Computer Science ISSN 19475500",
            "Computer Science ISSN 19475500",
            "Computer Science ISSN 19475500",
            ""
        ]
        for value in values:
            try:
                e = event.SetReportNumber(creator=self.user, report_num=value)
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle %s: %s' % (value, e))

    def test_invalid_values(self):
        """Some invalid values are passed."""
        values = [
            "not a report number",
        ]
        for value in values:
            with self.assertRaises(InvalidEvent):
                e = event.SetReportNumber(creator=self.user, report_num=value)
                e.validate(self.submission)


class TestSetJournalReference(TestCase):
    """Tests for :class:`.event.SetJournalReference`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_valid_journal_ref(self):
        """Valid journal ref values are used."""
        values = [
            "Phys. Rev. Lett. 104, 097003 (2010)",
            "Phys. Rev. B v81, 094405 (2010)",
            "Phys. Rev. D81 (2010) 036004",
            "Phys. Rev. A 74, 033822 (2006)Phys. Rev. A 74, 033822 (2006)Phys. Rev. A 74, 033822 (2006)Phys. Rev. A 81, 032303 (2010)",
            "Opt. Lett. 35, 499-501 (2010)",
            "Phys. Rev. D 81, 034023 (2010)",
            "Opt. Lett. Vol.31 (2010)",
            "Fundamental and Applied Mathematics, 14(8)(2008), 55-67. (in Russian)",
            "Czech J Math, 60(135)(2010), 59-76.",
            "PHYSICAL REVIEW B 81, 024520 (2010)",
            "PHYSICAL REVIEW B 69, 094524 (2004)",
            "Announced on Ap&SS, Oct. 2009",
            "Phys. Rev. Lett. 104, 095701 (2010)",
            "Phys. Rev. B 76, 205407 (2007).",
            "Extending Database Technology (EDBT) 2010",
            "Database and Expert Systems Applications (DEXA) 2009",
            "J. Math. Phys. 51 (2010), no. 3, 033503, 12pp",
            "South East Asian Bulletin of Mathematics, Vol. 33 (2009), 853-864.",
            "Acta Mathematica Academiae Paedagogiace NyÃ­regyhÃ¡ziensis, Vol. 25, No. 2 (2009), 189-190.",
            "Creative Mathematics and Informatics, Vol. 18, No. 1 (2009), 39-45.",
            ""
        ]
        for value in values:
            try:
                e = event.SetJournalReference(creator=self.user,
                                              journal_ref=value)
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle %s: %s' % (value, e))

    def test_invalid_values(self):
        """Some invalid values are passed."""
        values = [
            "Phys. Rev. Lett. 104, 097003 ()",
            "Phys. Rev. accept submit B v81, 094405 (2010)",
            "Phys. Rev. D81 036004",
        ]
        for value in values:
            with self.assertRaises(InvalidEvent):
                e = event.SetJournalReference(creator=self.user,
                                              journal_ref=value)
                e.validate(self.submission)


class TestSetACMClassification(TestCase):
    """Tests for :class:`.event.SetACMClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_valid_acm_class(self):
        """ACM classification value is valid."""
        values = [
            "H.2.4",
            "F.2.2; H.3.m",
            "H.2.8",
            "H.2.4",
            "G.2.1",
            "D.1.1",
            "G.2.2",
            "C.4",
            "I.2.4",
            "I.6.3",
            "D.2.8",
            "B.7.2",
            "D.2.4; D.3.1; D.3.2; F.3.2",
            "F.2.2; I.2.7",
            "G.2.2",
            "D.3.1; F.3.2",
            "F.4.1; F.4.2",
            "C.2.1; G.2.2",
            "F.2.2; G.2.2; G.3; I.6.1; J.3 ",
            "H.2.8; K.4.4; H.3.5",
            ""
        ]
        for value in values:
            try:
                e = event.SetACMClassification(creator=self.user,
                                               acm_class=value)
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle %s: %s' % (value, e))


class TestSetMSCClassification(TestCase):
    """Tests for :class:`.event.SetMSCClassification`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_valid_msc_class(self):
        """MSC classification value is valid."""
        values = [
            "57M25",
            "35k55; 35k65",
            "60G51",
            "16S15, 13P10, 17A32, 17A99",
            "16S15, 13P10, 17A30",
            "05A15 ; 30F10 ; 30D05",
            "16S15, 13P10, 17A01, 17B67, 16D10",
            "primary 05A15 ; secondary 30F10, 30D05.",
            "35B45 (Primary), 35J40 (Secondary)",
            "13D45, 13C14, 13Exx",
            "13D45, 13C14",
            "57M25; 05C50",
            "32G34 (Primary), 14D07 (Secondary)",
            "05C75, 60G09",
            "14H20; 13A18; 13F30",
            "49K10; 26A33; 26B20",
            "20NO5, 08A05",
            "20NO5 (Primary), 08A05 (Secondary)",
            "83D05",
            "20NO5; 08A05"
        ]
        for value in values:
            try:
                e = event.SetMSCClassification(creator=self.user,
                                               msc_class=value)
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle %s: %s' % (value, e))


class TestSetComments(TestCase):
    """Tests for :class:`.event.SetComments`."""

    def setUp(self):
        """Initialize auxiliary data for test cases."""
        self.user = agent.User(12345, 'uuser@cornell.edu')
        self.submission = submission.Submission(
            submission_id=1,
            creator=self.user,
            owner=self.user,
            created=datetime.now(UTC)
        )

    def test_empty_value(self):
        """Comment is set to an empty string."""
        e = event.SetComments(creator=self.user, comments='')
        try:
            e.validate(self.submission)
        except InvalidEvent as e:
            self.fail('Failed to handle empty comments')

    def test_reasonable_comment(self):
        """Comment is set to some reasonable value smaller than 400 chars."""
        for locale in LOCALES:
            comments = Text(locale=locale).text(20)[:400]
            e = event.SetComments(creator=self.user, comments=comments)
            try:
                e.validate(self.submission)
            except InvalidEvent as e:
                self.fail('Failed to handle comments: %s' % comments)

    def test_huge_comment(self):
        """Comment is set to something unreasonably large."""
        comments = Text().text(200)    # 200 sentences.
        e = event.SetComments(creator=self.user, comments=comments)
        with self.assertRaises(InvalidEvent):
            e.validate(self.submission)


# Locales supported by mimesis.
LOCALES = [
    "cs",
    "da",
    "de",
    "de-at",
    "de-ch",
    "el",
    "en",
    "en-au",
    "en-ca",
    "en-gb",
    "es",
    "es-mx",
    "et",
    "fa",
    "fi",
    "fr",
    "hu",
    "is",
    "it",
    "ja",
    "kk",
    "ko",
    "nl",
    "nl-be",
    "no",
    "pl",
    "pt",
    "pt-br",
    "ru",
    "sv",
    "tr",
    "uk",
    "zh",
]
