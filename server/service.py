"""Command service: the only code that reads or changes commands."""

from server.models import Command, CommandStatus


# Every allowed status change. Anything not listed here is illegal.
TRANSITIONS: dict[CommandStatus, set[CommandStatus]] = {
    CommandStatus.PENDING: {CommandStatus.DISPATCHED},
    CommandStatus.DISPATCHED: {
        CommandStatus.SUCCEEDED,
        CommandStatus.FAILED,
        CommandStatus.PENDING,  # lease expired, attempts left (TODO: will be implemented)
        CommandStatus.TIMED_OUT,  # lease expired, no attempts left (TODO: will be implemented)
    },
    CommandStatus.SUCCEEDED: set(),
    CommandStatus.FAILED: set(),
    CommandStatus.TIMED_OUT: set(),
}


class CommandNotFound(Exception):
    """Unknown id, or the command belongs to another agent."""


class InvalidTransition(Exception):
    """The requested status change is not in TRANSITIONS."""


def check_transition(current: CommandStatus, new: CommandStatus) -> None:
    """Guard the command lifecycle state machine."""
    if new not in TRANSITIONS[current]:
        raise InvalidTransition(f"{current.value} -> {new.value}")


def _set_status(command: Command, new_status: CommandStatus) -> None:
    """The only place a command's status changes."""
    check_transition(command.status, new_status)
    command.status = new_status
