"""Remote agent: polls the server for commands, simulates running them, reports results."""

import argparse
import time
from collections import OrderedDict
from datetime import datetime, timezone

import httpx

STATE = {"firmware_version": "1.0.0"}
BOOT = time.monotonic()


class ResultCache:
    """Ring buffer, keeps recently executed commands, so a re-delivered command never runs twice."""

    def __init__(self, size: int = 100) -> None:
        self.size = size
        self._items: OrderedDict[str, dict] = OrderedDict()

    def get(self, command_id: str) -> dict | None:
        return self._items.get(command_id)

    def put(self, command_id: str, outcome: dict) -> None:
        self._items[command_id] = outcome
        if len(self._items) > self.size:
            self._items.popitem(last=False)  # drop the oldest, so be a ring buffer :)


def handle_ping(payload: dict) -> dict:
    return {"pong": True, "agent_time": datetime.now(timezone.utc).isoformat()}


def handle_sleep(payload: dict) -> dict:
    seconds = float(payload.get("seconds", 1))
    time.sleep(seconds)
    return {"slept_s": seconds}


def handle_get_status(payload: dict) -> dict:
    import random

    return {
        "firmware_version": STATE["firmware_version"],
        "uptime_s": round(time.monotonic() - BOOT, 1),
        "cpu_temp_c": round(random.uniform(40.0, 60.0), 1),  # simulated sensor
    }


def handle_update_firmware(payload: dict) -> dict:
    version = payload[
        "version"
    ]  # dont use .get so if it's missing -> KeyError -> FAILED, which is correct
    time.sleep(float(payload.get("duration_s", 10)))  # simulated download + flash
    previous = STATE["firmware_version"]
    STATE["firmware_version"] = version
    return {"previous_version": previous, "firmware_version": version}


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
    except Exception as exc:  # noqa: BLE001 (ruff ignore)
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}


def run(server: str, agent_id: str, interval: float) -> None:
    cache = ResultCache()
    headers = {"X-Agent-Id": agent_id}
    with httpx.Client(base_url=server, headers=headers, timeout=10.0) as client:
        print(f"[{agent_id}] polling {server} every {interval}s")
        while True:
            try:
                response = client.get(
                    "/agent/v1/commands/next",
                    headers={"X-Firmware-Version": STATE["firmware_version"]},
                )
                if response.status_code == 204:
                    time.sleep(interval)
                    continue
                response.raise_for_status()
                command = response.json()
                print(f"[{agent_id}] got {command['type']} {command['id']}")

                command = response.json()
                outcome = cache.get(command["id"])
                if outcome is None:  # check if we executed the command before
                    print(
                        f"[{agent_id}] got {command['type']} {command['id']} (attempt {command['attempts']})"
                    )
                    outcome = execute(command)
                    cache.put(
                        command["id"], outcome
                    )  # save before reporting: the report may be lost
                else:
                    print(
                        f"[{agent_id}] {command['id']} already done, re-sending saved result"
                    )
                report(client, agent_id, command, outcome)
                print(f"[{agent_id}] reported {outcome['status']}")
            except httpx.HTTPError as exc:
                print(f"[{agent_id}] server error: {exc!r}, retrying in {interval}s")
                time.sleep(interval)


def report(client: httpx.Client, agent_id: str, command: dict, outcome: dict) -> None:
    """Send the outcome, fenced with the attempt number this delivery came with."""
    response = client.post(
        f"/agent/v1/commands/{command['id']}/result",
        json={**outcome, "attempt": command["attempts"]},
    )
    if response.status_code == 409:
        # Lease expired while we were working; the server will re-deliver,
        # and the cache will answer for us then
        print(
            f"[{agent_id}] result for {command['id']} rejected: {response.json()['detail']}"
        )
        return
    response.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulated fleet agent")
    parser.add_argument("--agent-id", default="agent-001")
    parser.add_argument("--firmware-version", default="1.0.0")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--interval", type=float, default=2.0, help="seconds between empty polls"
    )
    args = parser.parse_args()

    STATE["firmware_version"] = args.firmware_version

    try:
        run(args.server, args.agent_id, args.interval)
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    main()
