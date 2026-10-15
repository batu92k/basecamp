# Basecamp: fleet command server and agent

A proof of concept design for sending commands to remote devices and getting their results back.

- **API server** (FastAPI): queues commands per agent, hands them out, and tracks every
  command through an explicit state machine.
- **Remote agent** (Python): polls the server, simulates running commands, reports results.

The agent is built like device firmware: it only makes outbound connections, rides out
server outages with backoff, and never runs a re-delivered command twice.

## Quick start

Python 3.12 or newer (developed on Python 3.14 in WSL Ubuntu).

```bash
git clone https://github.com/batu92k/basecamp.git && cd basecamp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Three terminals, all from the repo root:

```bash
fastapi dev server/main.py                       # server on :8000, interactive API docs at /docs
python agent/agent.py --agent-id agent-001       # one simulated device
python scripts/send_command.py agent-001 ping    # send a command and wait for its result
```

## Testing

Everything runs on pytest and underneath, mainly FastAPI's TestClient is used.

```bash
python -m pytest -v
```


## Architecture

Operators push commands in, agents pull them out, and the command service in between is the
only code that reads or changes a command.

- [Big picture: for the PoC](docs/big-picture.md)
- [Happy path](docs/happy-path.md)
- [Command lifecycle](docs/state-machine.md)
- [Agent crashes mid-command](docs/agent-crash.md)

| Path | File | Role |
|---|---|---|
| `server/main.py` | API routes, error → HTTP mapping, reaper task | parse, call the service, return |
| `server/service.py` | state machine, leases, fencing, in-memory store | all the rules, no HTTP |
| `server/models.py` | Pydantic models and enums | shared objects |
| `agent/agent.py` | poll loop, handlers, dedup cache, backoff | the simulated device |
| `scripts/send_command.py` | operator CLI | send and wait |

## How reliability works

Delivery is **at-least-once**; the **effect happens once**.

1. **Leases.** A dispatched command belongs to its agent for 30 s (longer than the slowest command).

2. **Reaper.** Once a second, a background task returns expired leases to `PENDING`
   (it keeps its place in the queue), or marks the command `TIMED_OUT` after 3 attempts.
   It acts as the server's watchdog.

3. **Fencing.** Every result carries the attempt number it belongs to. A result from an
   attempt that was replaced gets `409`.

4. **Agent dedup cache.** The agent remembers the outcome of its last 100 commands. If a
   command comes back (lost result, slow agent), it re-sends the saved outcome with the new
   attempt number instead of running it again.

5. **Backoff with full jitter.** After a failure the agent waits a random time in
   an increasing time window, so a fleet coming back from an outage doesn't hit the
   server.

Every status change goes through one transition table in `service.py`; anything not in the
table is rejected with `409`.

## API

| Method and path | Who | Result |
|---|---|---|
| `POST /api/v1/agents/{agent_id}/commands` `{type, payload}` | operator | `202` + the command, `PENDING` |
| `GET /api/v1/commands/{command_id}` | operator | `200` status and result, `404` unknown |
| `GET /agent/v1/commands/next` | agent | `200` + command (starts its lease), `204` nothing waiting |
| `POST /agent/v1/commands/{command_id}/result` `{status, result, error, attempt}` | agent | `200`, `404` not yours, `409` stale attempt or invalid transition |


## Design decisions

- **Pull over push**: devices most probably will sit behind NAT and firewalls, so the agent opens every connection.

- **Short polling over long polling, WebSockets or MQTT**: PoC has the short polling which is simplest to build and test. Long polling is the next step. MQTT can be the choice (probably) after ~100,000 devices.

- **In-memory store behind a service layer over a database**: PoC scope. All access goes through `service.py`, so one the database solution like SQLite etc. selected, it can be implemented rather quick.

- **One event loop**: every endpoint and the reaper are `async def`, and no claim or completion contains an `await`, so each one is atomic.

- **Transition table over `if` ladders**: the rules are data; illegal state transitions become `409` in one place.

- **At-least-once + fencing + dedup over exactly-once delivery**: exactly-once delivery isn't possible over an unreliable network; an idempotent effect is.
- **Injected time**: service functions take `now`, so tests jump 30 s ahead instead of sleeping.
- **`404`, not `403`, for another agent's command**: don't reveal that it exists.

## Out of Scope for the PoC

 - **Persistent storage**: No database in PoC, only in-memory store. Which means if server restarts, it loses the commands. In addition, second server (if there is any added) can not see the command queue.

 - **Long polling**: Short polling only in PoC. With long polling, 'next' command can wait up-to 25 seconds, so server can keep the connection open for a long(er) time. Which reduces the amount of empty requests.

 - **Authentication**: There is no security feature in the PoC. Anyone who can reach the server can send commands, and `X-Agent-Id` can be spoofed. A compromised server can send bad commands. Also, a device can impersonate another. Later the following can be implemented:
   - Using mTLS (so extend HTTPS)
   - Commands can be signed by server and verified on the device
   - Operator should have an API key for starters then SSO per-user later on


