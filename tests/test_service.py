from datetime import datetime, timedelta, timezone

import pytest

from server import service
from server.models import Command, CommandStatus, CommandType

AGENT_001 = "agent-001"
AGENT_002 = "agent-002"
T0 = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)


def new_command(agent_id: str = AGENT_001, at: datetime = T0):
    """Create a command with default T0 time, this will be helpful when testing expiry feature"""
    return service.create_command(agent_id, CommandType.ping, {}, at)


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
            1,
            CommandStatus.SUCCEEDED,
            {},
            None,
            datetime.now(timezone.utc),
        )


def test_result_for_never_dispatched_command_is_stale():
    command: Command = service.create_command(
        AGENT_001, CommandType.ping, {}, datetime.now(timezone.utc)
    )
    with pytest.raises(service.StaleAttempt):
        service.complete_command(
            AGENT_001,
            command.id,
            1,
            CommandStatus.SUCCEEDED,
            {},
            None,
            datetime.now(timezone.utc),
        )


def test_lease_expiry_requeues_then_times_out():
    """Expire the lease of command until no more attempts left then expect timed out
    from command status"""
    command = new_command()
    now = T0
    for attempt in range(1, command.max_attempts + 1):
        claimed = service.claim_next(AGENT_001, now)
        assert claimed.attempts == attempt
        now = claimed.lease_expires_at  # jump straight to the deadline
        service.expire_leases(now)

    assert command.status == CommandStatus.TIMED_OUT
    assert service.claim_next(AGENT_001, now) is None  # never handed out again


def test_late_result_from_old_attempt_is_rejected():
    command = new_command()
    service.claim_next(AGENT_001, T0)  # attempt 1
    service.expire_leases(
        T0 + timedelta(seconds=service.LEASE_SECONDS)
    )  # back to PENDING
    service.claim_next(AGENT_001, T0 + timedelta(seconds=31))  # attempt 2

    # send the result from attempt 1 (which is already expired and placed to pending by reaper)
    with pytest.raises(service.StaleAttempt):
        service.complete_command(
            AGENT_001,
            command.id,
            1,
            CommandStatus.SUCCEEDED,
            {},
            None,
            T0 + timedelta(seconds=32),
        )

    # send the result for the current attempt
    done = service.complete_command(
        AGENT_001,
        command.id,
        2,
        CommandStatus.SUCCEEDED,
        {},
        None,
        T0 + timedelta(seconds=33),
    )
    assert done.status == CommandStatus.SUCCEEDED
