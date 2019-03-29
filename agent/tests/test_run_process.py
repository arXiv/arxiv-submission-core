"""Test running processes."""

from unittest import TestCase, mock

from .. import process
from ..runner import base, async


class TestProcess(TestCase):
    """Test running a process synchronously."""

    def setUp(self):
        """Given a synchronous process."""
        class FooProcess(process.Process):
            @process.step()
            def step_a(self, previous, trigger, emit):
                return trigger.event.some_value + 1

            @process.step()
            def step_b(self, previous, trigger, emit):
                return (previous + 1) ** 2

            @process.step()
            def step_c(self, previous, trigger, emit):
                if previous > 20:
                    self.fail(message='fail like it\'s 1999')
                return (previous + 1) ** 2

        self.FooProcess = FooProcess
        self.submission_id = 24543
        self.trigger = {
            'event': mock.MagicMock(submission_id=self.submission_id),
        }

    @mock.patch(f'{process.__name__}.AddProcessStatus', mock.MagicMock)
    @mock.patch(f'{base.__name__}.save')
    def test_call(self, mock_save):
        """Calling the process runs all steps in order."""
        saved_events = []

        def append_events(*events, submission_id=None):
            for event in events:
                saved_events.append((event, submission_id))

        mock_save.side_effect = append_events

        proc = self.FooProcess(self.submission_id)
        runner = base.ProcessRunner(proc)
        runner.run(mock.MagicMock(event=mock.MagicMock(some_value=1)))

        self.assertEqual(saved_events[0][0].status,
                         process.Process.Status.PENDING)
        self.assertEqual(saved_events[0][1], self.submission_id)
        self.assertEqual(saved_events[1][0].status,
                         process.Process.Status.IN_PROGRESS)
        self.assertEqual(saved_events[1][0].step, 'step_a')
        self.assertEqual(saved_events[1][1], self.submission_id)

        self.assertEqual(saved_events[2][0].status,
                         process.Process.Status.IN_PROGRESS)
        self.assertEqual(saved_events[2][0].step, 'step_b')
        self.assertEqual(saved_events[2][1], self.submission_id)

        self.assertEqual(saved_events[3][0].status,
                         process.Process.Status.SUCCEEDED)
        self.assertEqual(saved_events[3][0].step, 'step_c')
        self.assertEqual(saved_events[3][1], self.submission_id)

    @mock.patch(f'{process.__name__}.AddProcessStatus', mock.MagicMock)
    @mock.patch(f'{base.__name__}.save')
    def test_failing_process(self, mock_save):
        """Calling the process runs all steps in order, but one fails."""
        saved_events = []

        def append_events(*events, submission_id=None):
            for event in events:
                saved_events.append((event, submission_id))

        mock_save.side_effect = append_events

        proc = self.FooProcess(self.submission_id)
        runner = base.ProcessRunner(proc)
        runner.run(mock.MagicMock(event=mock.MagicMock(some_value=5)))

        self.assertEqual(saved_events[0][0].status,
                         process.Process.Status.PENDING)
        self.assertEqual(saved_events[0][1], self.submission_id)
        self.assertEqual(saved_events[1][0].status,
                         process.Process.Status.IN_PROGRESS)
        self.assertEqual(saved_events[1][0].step, 'step_a')
        self.assertEqual(saved_events[1][1], self.submission_id)

        self.assertEqual(saved_events[2][0].status,
                         process.Process.Status.IN_PROGRESS)
        self.assertEqual(saved_events[2][0].step, 'step_b')
        self.assertEqual(saved_events[2][1], self.submission_id)

        self.assertEqual(saved_events[3][0].status,
                         process.Process.Status.FAILED)
        self.assertEqual(saved_events[3][0].step, 'step_c')
        self.assertEqual(saved_events[3][1], self.submission_id)
