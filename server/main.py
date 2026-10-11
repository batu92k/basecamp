from datetime import datetime, timezone


from fastapi import Depends, FastAPI, Header, Request, Response, status
from fastapi.responses import JSONResponse
from server.models import (
    Command,
    CommandStatus,
    CommandCreate,
    CommandResult,
)

from server import service


app = FastAPI(title="Fleet Server API")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@app.exception_handler(service.CommandNotFound)
async def command_not_found(request: Request, exc: service.CommandNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Command not found"})


@app.exception_handler(service.InvalidTransition)
async def invalid_transition(request: Request, exc: service.InvalidTransition) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": f"Invalid transition: {exc}"})


# --- Endpoints ---


@app.get("/")
async def root():
    return {"message": "Basecamp"}


@app.post(
    "/api/v1/agents/{agent_id}/commands",
    response_model=Command,
    status_code=status.HTTP_202_ACCEPTED,  # accepted, but not done yet since we will handle the command
)
async def create_command(agent_id: str, body: CommandCreate) -> Command:
    return service.create_command(agent_id, body.type, body.payload, utcnow())


@app.get("/api/v1/commands/{command_id}", response_model=Command)
async def get_command(command_id: str) -> Command:
    return service.get_command(command_id)


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
    """Hand the agent its oldest pending command, or 204 if there is none."""
    command = service.claim_next(agent_id, utcnow())
    if command is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return command


@app.post("/agent/v1/commands/{command_id}/result", response_model=Command)
async def submit_result(
    command_id: str, body: CommandResult, agent_id: str = Depends(get_agent_id)
) -> Command:
    return service.complete_command(
        agent_id,
        command_id,
        CommandStatus(body.status),
        body.result,
        body.error,
        utcnow(),
    )
