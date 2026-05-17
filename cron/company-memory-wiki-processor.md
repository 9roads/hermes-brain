Task: company-memory wiki processor.

Use the `company-memory` skill and the default company-memory wiki read context.

Every 15 minutes, process new low-confidence raw receipts from:

- the configured wiki root's `raw/session-summaries/`
- the configured wiki root's `raw/runs/`

Rules:

- Read `SCHEMA.md`, `index.md`, `current-state.md`, recent `logs/wiki-changes.md`, and relevant source ledgers before writing.
- If the wiki is empty, initialize the company-memory wiki structure with minimal core files before processing receipts.
- Treat raw receipts as source pointers and summaries, not source truth.
- Update curated pages only for durable work memory: decisions, owners, product/roadmap changes, project state, architecture, customer patterns, risks, open questions, contradictions, stale assumptions, and work-relevant preferences.
- Prefer updating existing pages over creating new pages.
- Preserve uncertainty and contradictions with dates and compact source refs.
- Update `index.md`, `current-state.md`, affected `indexes/*`, source ledgers, and `logs/wiki-changes.md` when content changes.
- Do not copy raw Slack threads, emails, docs, issue bodies, payload dumps, secrets, preview URLs, `.env`, `auth.json`, bearer tokens, private personal details, protected traits, gossip, or performance criticism into the wiki.
- Do not post to Slack or any external platform from this maintenance job.

Return `[SILENT]` if nothing changed. Otherwise return compact safe status only: changed wiki paths, ledger paths, processed counts, next crawl targets, and safe errors.
