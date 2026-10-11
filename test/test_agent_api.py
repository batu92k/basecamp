import pytest
from fastapi.testclient import TestClient

from server.main import COMMANDS, CommandStatus, CommandType, app

client = TestClient(app)
AGENT_01 = {"X-Agent-Id": "agent-001"}
AGENT_02 = {"X-Agent-Id": "agent-002"}
NEXT = "/agent/v1/commands/next"


# clear commands in each test
@pytest.fixture(autouse=True)
def empty_store():
    COMMANDS.clear()


def create(agent_id: str = "agent-001", type_: str = "ping") -> str:
    response = client.post(f"/api/v1/agents/{agent_id}/commands", json={"type": type_})
    assert response.status_code == 202
    return response.json()["id"]


def report(command_id: str, status: str = "SUCCEEDED", headers: dict = AGENT_01):
    return client.post(
        f"/agent/v1/commands/{command_id}/result",
        headers=headers,
        json={"status": status},
    )


def test_next_returns_204_when_queue_is_empty():
    response = client.get(NEXT, headers=AGENT_01)

    assert response.status_code == 204
    assert response.content == b""  # expect no body content


def test_next_withour_the_header():
    response = client.get(NEXT, headers="")

    assert response.status_code == 422


def test_create_command_and_poll():
    command_id = create(agent_id=AGENT_01.get("X-Agent-Id", ""), type_=CommandType.ping)
    response = client.get(f"/api/v1/commands/{command_id}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id

    response_json = client.get(NEXT, headers=AGENT_01).json()

    assert response_json["status"] == CommandStatus.DISPATCHED


def test_report_different_result():
    #  create a command
    command_id = create(agent_id=AGENT_01.get("X-Agent-Id", ""), type_=CommandType.ping)
    response = client.get(f"/api/v1/commands/{command_id}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id

    #  poll the command
    response_json = client.get(NEXT, headers=AGENT_01).json()

    assert response_json["status"] == CommandStatus.DISPATCHED

    # report success
    response = report(
        command_id=command_id, status=CommandStatus.SUCCEEDED, headers=AGENT_01
    )

    assert response.status_code == 200

    # report failure for the same command and get 409
    response = report(
        command_id=command_id, status=CommandStatus.FAILED, headers=AGENT_01
    )

    assert response.status_code == 409


def test_report_for_still_pending_command():
    #  create a command
    command_id = create(agent_id=AGENT_01.get("X-Agent-Id", ""), type_=CommandType.ping)
    response = client.get(f"/api/v1/commands/{command_id}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id

    # report success and expect 409 (conflict)
    response = report(
        command_id=command_id, status=CommandStatus.SUCCEEDED, headers=AGENT_01
    )

    assert response.status_code == 409


def test_agent_reports_another_agents_command():
    #  create a command for agent 001
    command_id_agent_01 = create(
        agent_id=AGENT_01.get("X-Agent-Id", ""), type_=CommandType.ping
    )
    response = client.get(f"/api/v1/commands/{command_id_agent_01}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id_agent_01

    #  create a command for agent 002
    command_id_agent_02 = create(
        agent_id=AGENT_02.get("X-Agent-Id", ""), type_=CommandType.ping
    )
    response = client.get(f"/api/v1/commands/{command_id_agent_02}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id_agent_02

    # agent 001 reports agent 002's command
    response = report(
        command_id=command_id_agent_02, status=CommandStatus.SUCCEEDED, headers=AGENT_01
    )

def test_agent_polls_next_without_header():
    #  create a command
    command_id = create(agent_id=AGENT_01.get("X-Agent-Id", ""), type_=CommandType.ping)
    response = client.get(f"/api/v1/commands/{command_id}")
    response_json = response.json()

    assert response.status_code == 200
    assert response_json["status"] == CommandStatus.PENDING
    assert response_json["id"] == command_id

    #  poll the command
    response = client.get(NEXT, headers=None)

    assert response.status_code == 422
