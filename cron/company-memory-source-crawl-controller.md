Task: company-memory source crawl controller.

Use the `company-memory` skill, Composio MCP, and the adaptive policy emitted by the pre-check script.

Goal: discover recent, interesting, or patterned company-tool activity and write safe raw ingestion artifacts to the configured wiki root's `raw/runs/` for later wiki processing.

Rules:

- Use Composio MCP and remote workbench capabilities for connected company tools.
- Discover connected toolkits and available read/list/search/detail tools.
- Classify tools before use. Use only read-only tools by default.
- Reject mutating actions matching send, create, update, delete, archive, label, invite, post, react, share, approve, or permission changes unless a future explicit user-approved feature allows them.
- Discover containers first: channels, repos, projects, folders, boards, labels, databases, or equivalent toolkit containers.
- Breadth-list recent objects, rank high-signal items, and depth-read only capped candidates.
- Use bounded subagents only inside the run when multiple hot toolkits need parallel inspection; the parent remains the single writer.
- Emit compact summaries, provenance, source refs, timestamps, hashes, scores, pattern tags, entities, and redaction metadata.
- Do not store full Slack threads, email bodies, docs dumps, ticket bodies, provider payloads, secrets, long excerpts, or private personal details.
- Update the configured wiki root's `raw/_state/adaptive-policy.json`, cursors, ledgers, and next crawl targets.
- Leave enough Composio rate-limit budget for user-facing work.

Return `[SILENT]` if no useful crawl occurred. Otherwise return compact safe status only.
