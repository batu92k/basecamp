import uuid
from datetime import datetime, timezone


from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from server.models import (
    Command,
    CommandStatus,
    CommandCreate,
    CommandResult,
    TERMINAL_STATUSES,
)


app = FastAPI(title="Fleet Server API")


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
async def create_command(agent_id: str, body: CommandCreate) -> Command:
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


@app.get("/api/v1/commands/{command_id}", response_model=Command)
async def get_command(command_id: str) -> Command:
    command = COMMANDS.get(command_id)
    if command is None:
        # Unknown id: return a proper 404, so don't crash
        raise HTTPException(status_code=404, detail="Command not found")
    return command


# --- Agent API ---


def get_agent_id(x_agent_id: str = Header()) -> str:
    """Who is calling. Placeholder: trusts a header. Later replace this with a token check."""
    return x_agent_id


@app.get(
    "/agent/v1/commands/next",
    response_model=Command,
    responses={204: {"description": "No command waiting"}},
)
async def next_command(agent_id: str = Depends(get_agent_id)):
    """Find oldest command pending for specific agent and dispatch it"""
    for command in COMMANDS.values():  # dicts keep insertion order: oldest first
        if command.agent_id == agent_id and command.status == CommandStatus.PENDING:
            command.status = CommandStatus.DISPATCHED
            command.dispatched_at = datetime.now(timezone.utc)
            return command
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/agent/v1/commands/{command_id}/result", response_model=Command)
async def submit_result(
    command_id: str, body: CommandResult, agent_id: str = Depends(get_agent_id)
) -> Command:
    command = COMMANDS.get(command_id)
    if command is None or command.agent_id != agent_id:
        # it is important to cover whether if the command exist but belong to another agent
        raise HTTPException(status_code=404, detail="Command not found")

    new_status = CommandStatus(body.status)
    if command.status in TERMINAL_STATUSES:
        if command.status == new_status:
            return (
                command  # duplicate report (like a lost reply): accept, change nothing
            )
        raise HTTPException(  # mismatched terminal state...
            status_code=409, detail=f"Command already {command.status.value}"
        )
    if command.status != CommandStatus.DISPATCHED:
        raise HTTPException(status_code=409, detail="Command was never dispatched")

    command.status = new_status
    command.result = body.result
    command.error = body.error
    command.completed_at = datetime.now(timezone.utc)
    return command
