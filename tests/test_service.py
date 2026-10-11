import pytest
from server import service
from server.models import CommandStatus


@pytest.fixture(autouse=True)
def empty_store():
    service.reset()


@pytest.mark.parametrize(
    "current, new",
    [
        (CommandStatus.PENDING, CommandStatus.DISPATCHED),
        (CommandStatus.DISPATCHED, CommandStatus.SUCCEEDED),
        (CommandStatus.DISPATCHED, CommandStatus.FAILED),
        (CommandStatus.DISPATCHED, CommandStatus.PENDING),
        (CommandStatus.DISPATCHED, CommandStatus.TIMED_OUT),
    ],
)
def test_allowed_transitions(current, new):
    service.check_transition(current, new)  # must not raise


@pytest.mark.parametrize(
    "current, new",
    [
        (CommandStatus.PENDING, CommandStatus.SUCCEEDED),
        (CommandStatus.SUCCEEDED, CommandStatus.FAILED),
        (CommandStatus.FAILED, CommandStatus.PENDING),
        (CommandStatus.TIMED_OUT, CommandStatus.DISPATCHED),
    ],
)
def test_illegal_transitions(current, new):
    with pytest.raises(service.InvalidTransition):
        service.check_transition(current, new)
