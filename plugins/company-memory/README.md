# Company Memory Wiki Lifecycle Plugin

This plugin keeps the company-memory profile independent from the bundled `llm-wiki` skill while preserving the useful read/orientation behavior.

The company-memory wiki is intended to become a living, source-grounded model of the company: what the company does, who works on what, how people collaborate, which tools and systems matter, who the customers are, what decisions have been made, and what is stale, risky, contested, or unknown.

It does four things:

1. Pre-creates the default wiki scaffold under `COMPANY_MEMORY_WIKI_ROOT` when Hermes starts, without overwriting existing pages.
2. Injects company-memory wiki read context at the start of every session.
3. Buffers compact, redacted turn metadata.
4. Writes one safe session-summary receipt to `raw/session-summaries/` when a session finalizes.

The runtime must set:

- `COMPANY_MEMORY_WIKI_ROOT`, normally `/mnt/company-memory-wiki`

Session summaries use the main Hermes model. The plugin does not configure or select a separate summary model.

The receipt is a low-confidence raw source. The scheduled company-memory wiki processor decides whether it should update curated wiki pages.

## Wiki Scaffold

The scaffold creates the core directories and minimal orientation pages:

- `SCHEMA.md`, `index.md`, `current-state.md`
- `indexes/agent-map.md`, `indexes/by-source.md`, `indexes/by-entity.md`, `indexes/stale-and-contested.md`, `indexes/open-questions.md`
- `sources/source-registry.md`
- `company/`, `team/`, `tools/`, `customers/`, `projects/`, `decisions/`, `architecture/`, `product/`, `entities/`, `processes/`, `risks/`, `questions/`, `summaries/`, `archive/`
- `raw/session-summaries/`, `raw/runs/`, `raw/_state/`
- `logs/wiki-changes.md`

`team/` is the first-class place for people, teams, ownership, decision rights, collaboration patterns, and work-relevant preferences. `entities/` is a broader cross-reference area for people, teams, customers, vendors, tools, products, repos, and systems.
