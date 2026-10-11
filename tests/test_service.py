from datetime import datetime, timezone

import pytest

from server import service
from server.models import Command, CommandStatus, CommandType

AGENT_001 = "agent-001"
AGENT_002 = "agent-002"


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


def test_claim_with_empty_store():
    assert service.claim_next(AGENT_001, datetime.now(timezone.utc)) == None


def test_agent_claims_while_only_command_exist_is_for_another_agent():
    """Yes, it is like a sentence but it's self explanatory, chars are pretty cheap nowadays :)"""
    service.create_command(AGENT_001, CommandType.ping, {}, datetime.now(timezone.utc))
    assert service.claim_next(AGENT_002, datetime.now(timezone.utc)) == None


def test_agent_completes_another_agents_command():
    service.create_command(AGENT_001, CommandType.ping, {}, datetime.now(timezone.utc))

    command_claimed: Command | None = service.claim_next(
        AGENT_001, datetime.now(timezone.utc)
    )

    assert command_claimed != None
    assert command_claimed.status == CommandStatus.DISPATCHED

    with pytest.raises(service.CommandNotFound):
        service.complete_command(
            AGENT_002,
            command_claimed.id,
            CommandStatus.SUCCEEDED,
            {},
            None,
            datetime.now(timezone.utc),
        )


def test_complete_pending_command():
    command: Command = service.create_command(
        AGENT_001, CommandType.ping, {}, datetime.now(timezone.utc)
    )
    with pytest.raises(service.InvalidTransition):
        service.complete_command(
            AGENT_001,
            command.id,
            CommandStatus.SUCCEEDED,
            {},
            None,
            datetime.now(timezone.utc),
        )
