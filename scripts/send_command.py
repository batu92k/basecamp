"""Send one command to an agent and wait for its result."""

import argparse
import json
import sys
import time

import httpx

TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT"}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send a command and wait for the result"
    )
    parser.add_argument("agent_id")
    parser.add_argument("type", help="ping, sleep, get_status")
    parser.add_argument("--payload", default="{}", help="JSON, e.g. '{\"seconds\": 3}'")
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    with httpx.Client(base_url=args.server, timeout=10.0) as client:
        response = client.post(
            f"/api/v1/agents/{args.agent_id}/commands",
            json={"type": args.type, "payload": json.loads(args.payload)},
        )
        response.raise_for_status()
        command = response.json()
        print(f"queued {command['id']}")

        deadline = time.monotonic() + args.timeout
        while command["status"] not in TERMINAL:
            if time.monotonic() > deadline:
                print(f"gave up after {args.timeout}s, last status {command['status']}")
                return 2
            time.sleep(0.5)
            command = client.get(f"/api/v1/commands/{command['id']}").json()

    print(json.dumps(command, indent=2))
    return 0 if command["status"] == "SUCCEEDED" else 1


if __name__ == "__main__":
    sys.exit(main())
