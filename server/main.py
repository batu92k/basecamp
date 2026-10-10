from fastapi import FastAPI
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

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

@app.get("/")
async def root():
    return {"message": "Basecamp"}
