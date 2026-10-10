import pytest
from fastapi.testclient import TestClient

from server.main import COMMANDS, CommandType, app, Command, CommandStatus

client = TestClient(app)
AGENT = {"X-Agent-Id": "agent-001"}
NEXT = "/agent/v1/commands/next"


# clear commands in each test
@pytest.fixture(autouse=True)
def empty_store():
    COMMANDS.clear()


def create(agent_id: str = "agent-001", type_: str = "ping") -> str:
    response = client.post(f"/api/v1/agents/{agent_id}/commands", json={"type": type_})
    assert response.status_code == 202
    return response.json()["id"]


def report(command_id: str, status: str = "SUCCEEDED", headers: dict = AGENT):
    return client.post(
        f"/agent/v1/commands/{command_id}/result",
        headers=headers,
        json={"status": status},
    )


def test_next_returns_204_when_queue_is_empty():
    response = client.get(NEXT, headers=AGENT)

    assert response.status_code == 204
    assert response.content == b""  # expect no body content


def test_next_withour_the_header():
    response = client.get(NEXT, headers="")

    assert response.status_code == 422


def test_create_command_and_poll():
    command_id = create(agent_id=AGENT.get("X-Agent-Id", ""), type_=CommandType.ping)
    response = client.get(f"/api/v1/commands/{command_id}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id

    response_json = client.get(NEXT, headers=AGENT).json()

    assert response_json["status"] == CommandStatus.DISPATCHED
    


