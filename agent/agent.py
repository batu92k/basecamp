"""Remote agent: polls the server for commands, simulates running them, reports results."""

import argparse
import time
from datetime import datetime, timezone

import httpx


def handle_ping(payload: dict) -> dict:
    return {"pong": True, "agent_time": datetime.now(timezone.utc).isoformat()}


def handle_sleep(payload: dict) -> dict:
    seconds = float(payload.get("seconds", 1))
    time.sleep(seconds)
    return {"slept_s": seconds}


HANDLERS = {
    "ping": handle_ping,
    "sleep": handle_sleep,
}


def execute(command: dict) -> dict:
    """Run one command and build the result body. Never raises."""
    handler = HANDLERS.get(command["type"])
    if handler is None:
        return {
            "status": "FAILED",
            "error": f"unsupported command type: {command['type']}",
        }
    try:
        return {"status": "SUCCEEDED", "result": handler(command["payload"])}
    except Exception as exc:
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}


def run(server: str, agent_id: str, interval: float) -> None:
    headers = {"X-Agent-Id": agent_id}
    with httpx.Client(base_url=server, headers=headers, timeout=10.0) as client:
        print(f"[{agent_id}] polling {server} every {interval}s")
        while True:
            try:
                response = client.get("/agent/v1/commands/next")
                if response.status_code == 204:
                    time.sleep(interval)
                    continue
                response.raise_for_status()
                command = response.json()
                print(f"[{agent_id}] got {command['type']} {command['id']}")

                outcome = execute(command)
                client.post(
                    f"/agent/v1/commands/{command['id']}/result", json=outcome
                ).raise_for_status()
                print(f"[{agent_id}] reported {outcome['status']}")
            except httpx.HTTPError as exc:
                print(f"[{agent_id}] server error: {exc!r}, retrying in {interval}s")
                time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated fleet agent")
    parser.add_argument("--agent-id", default="agent-001")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="seconds between empty polls"
    )
    args = parser.parse_args()
    try:
        run(args.server, args.agent_id, args.interval)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
