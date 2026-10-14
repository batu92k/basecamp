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
git clone <repo-url> && cd basecamp
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Three terminals, all from the repo root:

```bash
fastapi dev server/main.py                       # server on :8000, interactive API docs at /docs
python agent/agent.py --agent-id agent-001       # one simulated device
python scripts/send_command.py agent-001 ping    # send a command and wait for its result
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
