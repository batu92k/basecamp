from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class CommandType(str, Enum):
    """Anything apart form this command set will get 422"""

    ping = "ping"
    sleep = "sleep"
    get_status = "get_status"


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


class CommandCreate(BaseModel):
    """What the operator sends in the POST body."""

    type: CommandType
    payload: dict = Field(default_factory=dict)  # e.g. {"seconds": 3} for sleep


class Command(BaseModel):
    """What the server stores and returns."""

    id: str
    agent_id: str
    type: CommandType
    payload: dict
    status: CommandStatus
    result: dict | None = None
    error: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime
    dispatched_at: datetime | None = None
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None


class CommandResult(BaseModel):
    """What the agent sends back when it has finished a command."""

    status: Literal["SUCCEEDED", "FAILED"]
    result: dict | None = None
    error: str | None = None


# these are the command statuses that can never change again
TERMINAL_STATUSES = {CommandStatus.SUCCEEDED, CommandStatus.FAILED, CommandStatus.TIMED_OUT}