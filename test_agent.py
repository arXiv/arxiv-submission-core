from unittest import mock
from agent import tasks, domain


if __name__ == '__main__':
    creator = mock.MagicMock()
    proc = tasks.FooProcess(5)
    runner = tasks.AsyncProcessRunner(proc)
    trigger = domain.Trigger()
    runner.run(trigger)
