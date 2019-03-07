from unittest import TestCase

import json

from ...serializer import dumps, loads
from ...domain.event import CreateSubmission
from ...domain.agent import User


class TestDumpLoad(TestCase):
    """Tests for :func:`.dumps` and :func:`.loads`."""

    def test_dump_createsubmission(self):
        """Serialize a :class:`.CreateSubmission` event."""
        user = User('123', 'foo@user.com', 'foouser')
        event = CreateSubmission(creator=user)
        data = dumps(event)
        self.assertDictEqual(user.to_dict(), json.loads(data)["creator"],
                             "User data is fully encoded")

        self.assertEqual(loads(data), event)
