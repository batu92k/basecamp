from fastapi import FastAPI
from enum import Enum

app = FastAPI(title="Fleet Server API")


class CommandType(str, Enum):
    # anything apart form this command set will get 422
    ping = "ping"
    sleep = "sleep"
    get_status = "get_status"


class CommandStatus(str, Enum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


@app.get("/")
async def root():
    return {"message": "Basecamp"}
