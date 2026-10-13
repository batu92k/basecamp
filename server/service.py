"""Command service: the only code that reads or changes commands."""

import uuid
from datetime import datetime, timedelta

from server.models import Agent, Command, CommandStatus, CommandType

LEASE_SECONDS = 30  # must be longer than the slowest command
COMMANDS: dict[str, Command] = {}  # well... pre-database solution for now :)
AGENTS: dict[str, Agent] = {}

# Every allowed status change. Anything not listed here is illegal.
TRANSITIONS: dict[CommandStatus, set[CommandStatus]] = {
    CommandStatus.PENDING: {CommandStatus.DISPATCHED},
    CommandStatus.DISPATCHED: {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.PENDING,  # lease expired, attempts left
        CommandStatus.TIMED_OUT,  # lease expired, no attempts left
    },
    CommandStatus.SUCCEEDED: set(),
    CommandStatus.FAILED: set(),
    CommandStatus.TIMED_OUT: set(),
}


class CommandNotFound(Exception):
    """Unknown id, or the command belongs to another agent."""


class InvalidTransition(Exception):
    """The requested status change is not in TRANSITIONS."""


class StaleAttempt(Exception):
    """A result for an attempt that is no longer the current one."""


def check_transition(current: CommandStatus, new: CommandStatus) -> None:
    """Guard the command lifecycle state machine."""
    if new not in TRANSITIONS[current]:
        raise InvalidTransition(f"{current.value} -> {new.value}")


def _set_status(command: Command, new_status: CommandStatus) -> None:
    """The only place a command's status changes."""
    check_transition(command.status, new_status)
    command.status = new_status


def reset() -> None:
    """Empty the store. Will be used by tests."""
    COMMANDS.clear()
    AGENTS.clear()


def create_command(
    agent_id: str, type_: CommandType, payload: dict, now: datetime
) -> Command:
    command = Command(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        type=type_,
        payload=payload,
        status=CommandStatus.PENDING,
        created_at=now,
    )
    COMMANDS[command.id] = command
    return command


def get_command(command_id: str) -> Command:
    command = COMMANDS.get(command_id)
    if command is None:
        raise CommandNotFound(command_id)
    return command


def claim_next(agent_id: str, now: datetime) -> Command | None:
    """Hand the agent its oldest PENDING command, or None if there is nothing."""
    for command in COMMANDS.values():  # dicts keep insertion order: oldest first
        if command.agent_id == agent_id and command.status == CommandStatus.PENDING:
            _set_status(command, CommandStatus.DISPATCHED)
            command.attempts += 1
            command.dispatched_at = now
            command.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
            return command
    return None


def complete_command(
    agent_id: str,
    command_id: str,
    attempt: int,
    new_status: CommandStatus,
    result: dict | None,
    error: str | None,
    now: datetime,
) -> Command:
    command = get_command(command_id)
    if command.agent_id != agent_id:
        raise CommandNotFound(command_id)  # 404, not 403: don't reveal it exists
    if command.status == new_status:
        return command  # duplicate report (lost reply, agent retried): accept, change nothing
    if attempt != command.attempts:
        raise StaleAttempt(f"attempt {attempt}, current is {command.attempts}")

    _set_status(command, new_status)
    command.result = result
    command.error = error
    command.completed_at = now
    return command


def expire_leases(now: datetime) -> list[Command]:
    """Watchdog: re-queue or time out every command whose lease ran out.

    Returns the commands it changed, so the caller can log them.
    """
    changed = []
    for command in COMMANDS.values():
        if command.status != CommandStatus.DISPATCHED or command.lease_expires_at > now:
            continue
        if command.attempts < command.max_attempts:
            _set_status(
                command, CommandStatus.PENDING
            )  # retry; keeps its place in the queue
        else:
            _set_status(command, CommandStatus.TIMED_OUT)
            command.error = f"lease expired {command.attempts} times"
            command.completed_at = now
        command.lease_expires_at = None
        changed.append(command)
    return changed


def touch_agent(agent_id: str, firmware_version: str | None, now: datetime) -> Agent:
    """Heartbeat: record that this agent is alive, and what it is running."""
    agent = AGENTS.get(agent_id)
    if agent is None:
        agent = Agent(id=agent_id, last_seen_at=now)
        AGENTS[agent_id] = agent
    agent.last_seen_at = now
    if firmware_version is not None:
        agent.firmware_version = firmware_version
    print(AGENTS)  # Keep it for debugging reasons
    return agent
