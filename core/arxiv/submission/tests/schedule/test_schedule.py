"""Tests for :mod:`.schedule`."""

from unittest import TestCase
from datetime import datetime, timedelta
from pytz import timezone, UTC
from ... import schedule

ET = timezone('US/Eastern')


class TestSchedule(TestCase):
    """Verify that scheduling functions work as expected."""

    def test_monday_morning(self):
        """E-print was submitted on Monday morning."""
        submitted = ET.localize(datetime(2019, 3, 18, 9, 47, 0))
        self.assertEqual(schedule.next_announcement_time(submitted),
                         ET.localize(datetime(2019, 3, 18, 20, 0, 0)),
                         "Will be announced at 8pm this evening")
        self.assertEqual(schedule.next_freeze_time(submitted),
                         ET.localize(datetime(2019, 3, 18, 14, 0, 0)),
                         "Freeze time is 2pm this afternoon")

    def test_monday_late_afternoon(self):
        """E-print was submitted on Monday in the late afternoon."""
        submitted = ET.localize(datetime(2019, 3, 18, 15, 32, 0))
        self.assertEqual(schedule.next_announcement_time(submitted),
                         ET.localize(datetime(2019, 3, 19, 20, 0, 0)),
                         "Will be announced at 8pm tomorrow evening")
        self.assertEqual(schedule.next_freeze_time(submitted),
                         ET.localize(datetime(2019, 3, 19, 14, 0, 0)),
                         "Freeze time is 2pm tomorrow afternoon")

    def test_monday_evening(self):
        """E-print was submitted on Monday in the evening."""
        submitted = ET.localize(datetime(2019, 3, 18, 22, 32, 0))
        self.assertEqual(schedule.next_announcement_time(submitted),
                         ET.localize(datetime(2019, 3, 19, 20, 0, 0)),
                         "Will be announced at 8pm tomorrow evening")
        self.assertEqual(schedule.next_freeze_time(submitted),
                         ET.localize(datetime(2019, 3, 19, 14, 0, 0)),
                         "Freeze time is 2pm tomorrow afternoon")

    def test_saturday(self):
        """E-print was submitted on a Saturday."""
        submitted = ET.localize(datetime(2019, 3, 23, 22, 32, 0))
        self.assertEqual(schedule.next_announcement_time(submitted),
                         ET.localize(datetime(2019, 3, 25, 20, 0, 0)),
                         "Will be announced at 8pm next Monday")
        self.assertEqual(schedule.next_freeze_time(submitted),
                         ET.localize(datetime(2019, 3, 25, 14, 0, 0)),
                         "Freeze time is 2pm next Monday")

    def test_friday_afternoon(self):
        """E-print was submitted on a Friday in the early afternoon."""
        submitted = ET.localize(datetime(2019, 3, 22, 13, 32, 0))
        self.assertEqual(schedule.next_announcement_time(submitted),
                         ET.localize(datetime(2019, 3, 24, 20, 0, 0)),
                         "Will be announced at 8pm on Sunday")
        self.assertEqual(schedule.next_freeze_time(submitted),
                         ET.localize(datetime(2019, 3, 22, 14, 0, 0)),
                         "Freeze time is 2pm that same day")
