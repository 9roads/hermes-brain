# Phoenix OpenViking Memory Provider

`openviking_memory` is the Phoenix general-purpose OpenViking memory provider
for Hermes. It uses the local OpenViking server as the canonical memory,
resource, and session archive backend.

The provider does not expose model tools. It keeps automatic session sync,
prefetch, compression/session-end commits, and built-in memory write mirroring
inside Hermes. Interactive memory/resource work should go through the
profile-owned `loisa-viking-cli` skill and OpenViking CLI.

Provider prefetch remains all-context internally. CLI skill guidance tells the
agent not to search `viking://session` for ordinary memory lookup; use durable
user memories and reusable resources instead.

Runtime defaults:

- endpoint: `http://127.0.0.1:1933`
- account: `default`
- user namespace: `default`
- internal agent id: `OPENVIKING_AGENT_ID`, then `hermes-memory`

`OPENVIKING_AGENT` is intentionally ignored. The agent id is provenance, not a
memory namespace.
