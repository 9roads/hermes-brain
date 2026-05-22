# Company Memory Wiki Read Context

The bundled `llm-wiki` skill is disabled for this profile. Use this company-memory read behavior in every session.

1. Treat the company-memory wiki as the default memory.
2. Understand the wiki's purpose: over time it should become a compact, source-grounded model of the company, including what the company does, who works on what, how people collaborate, which tools they use, who their customers are, what they value, and what is stale, risky, contested, or unknown.
3. Orient with `SCHEMA.md`, `index.md`, `current-state.md`, recent `logs/wiki-changes.md`, `indexes/stale-and-contested.md`, and source ledgers when they exist.
4. Answer from curated wiki pages first when they are sufficient and not stale.
5. Search Markdown files under the wiki when `index.md` may be incomplete.
6. Use `team/` for work-relevant people and teams; use `entities/` for broad cross-references across people, teams, customers, vendors, tools, products, repos, and systems.
7. Use compact wiki page references instead of pasted source excerpts.
8. Use the `composio-cli` skill with the injected Tool Router session for live reads only when the user asks for current state, the wiki is stale or contested, the answer depends on a source object, or answering from the wiki would be a guess.
9. Treat `raw/` as immutable source-receipt space. Do not edit raw receipts except when this plugin creates a session-summary receipt.
10. Do not copy raw provider content, full threads, long documents, emails, issue bodies, secrets, preview URLs, `.env`, `auth.json`, or bearer tokens into responses or wiki pages.
11. Do not store private personal details, protected traits, compensation, gossip, psychological labels, or performance criticism.
12. When evidence conflicts, preserve the contradiction with dates and source references.
13. Keep direct user replies short and platform-native unless the user asks for a deep report.
