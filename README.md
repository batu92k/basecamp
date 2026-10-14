# Basecamp: fleet command server and agent

A proof of concept design for sending commands to remote devices and getting their results back.

- **API server** (FastAPI): queues commands per agent, hands them out, and tracks every
  command through an explicit state machine.
- **Remote agent** (Python): polls the server, simulates running commands, reports results.

The agent is built like device firmware: it only makes outbound connections, rides out
server outages with backoff, and never runs a re-delivered command twice.

