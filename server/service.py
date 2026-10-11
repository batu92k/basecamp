"""Command service: the only code that reads or changes commands."""

from server.models import CommandStatus


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
