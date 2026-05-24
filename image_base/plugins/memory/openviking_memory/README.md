# Phoenix OpenViking Memory Provider

`openviking_memory` is the Phoenix general-purpose OpenViking memory provider
for Hermes. It uses the local OpenViking server as the canonical memory,
resource, and session archive backend.

The provider exposes model tools:

- `loisa_memory_search`
- `loisa_memory_read`
- `loisa_memory_list`
- `loisa_memory_grep`
- `loisa_memory_add_resource`
- `loisa_memory_capture`

Search is intentionally all-context: the provider sends `target_uri:
viking://` and does not expose model-selectable scope. List and grep provide
deterministic browsing and exact text/regex search for known `viking://` paths.
Resource ingestion is async from model tool calls, and explicit captures are
written to structured capture sessions before being committed through
OpenViking extraction.

Runtime defaults:

- endpoint: `http://127.0.0.1:1933`
- account: `default`
- user namespace: `default`
- internal agent id: `OPENVIKING_AGENT_ID`, then `hermes-memory`

`OPENVIKING_AGENT` is intentionally ignored. The agent id is provenance, not a
memory namespace.
