from fastapi import FastAPI, status
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid


app = FastAPI(title="Fleet Server API")


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
    created_at: datetime


# --- Endpoints ---

COMMANDS: dict[str, Command] = {}  # well... pre-database solution for now :)


@app.get("/")
async def root():
    return {"message": "Basecamp"}


@app.post(
    "/api/v1/agents/{agent_id}/commands",
    response_model=Command,
    status_code=status.HTTP_202_ACCEPTED,  # accepted, but not done yet since we will handle the command
)
def create_command(agent_id: str, body: CommandCreate) -> Command:
    # agent_id comes from the URL path, body is parsed and validated from JSON.
    command = Command(
        id=str(uuid.uuid4()),  # unique id the caller uses to ask for the result
        agent_id=agent_id,
        type=body.type,
        payload=body.payload,
        status=CommandStatus.PENDING,  # waits here until an agent fetches it
        created_at=datetime.now(timezone.utc),
    )
    COMMANDS[command.id] = command
    return command
