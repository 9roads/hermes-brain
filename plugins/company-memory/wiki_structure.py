from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path


CORE_DIRECTORIES = (
    "indexes",
    "raw/session-summaries",
    "raw/runs",
    "raw/_state",
    "sources",
    "company",
    "team",
    "tools",
    "projects",
    "decisions",
    "architecture",
    "product",
    "customers",
    "entities",
    "processes",
    "risks",
    "questions",
    "summaries",
    "logs",
    "archive",
)


def ensure_wiki_structure(wiki_root: Path, now: datetime | None = None) -> list[Path]:
    timestamp = now or datetime.now(timezone.utc)
    created: list[Path] = []

    for relative_directory in CORE_DIRECTORIES:
        directory = wiki_root / relative_directory

        if directory.exists():
            if not directory.is_dir():
                raise NotADirectoryError(f"company-memory wiki path is not a directory: {directory}")
            continue

        directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)

    for relative_file, content in default_pages(timestamp).items():
        path = wiki_root / relative_file

        if path.exists():
            if not path.is_file():
                raise IsADirectoryError(f"company-memory wiki path is not a file: {path}")
            continue

        atomic_write_text(path, content)
        created.append(path)

    return created


def default_pages(now: datetime) -> dict[str, str]:
    date = now.date().isoformat()
    timestamp = now.isoformat()

    return {
        "SCHEMA.md": f"""---
title: Company Memory Wiki Schema
type: schema
status: active
confidence: high
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, wiki, schema]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Wiki Schema

The company-memory wiki is a source-grounded company memory. It should become a compact, durable model of the company: what it does, who works on what, how people collaborate, which tools and systems matter, who the customers are, what decisions have been made, and what is stale, risky, contested, or unknown.

## Lifecycle

1. `raw/` stores immutable low-confidence source receipts, safe summaries, hashes, cursors, counts, and provenance.
2. The scheduled wiki processor promotes corroborated durable facts into curated Markdown pages.
3. Curated pages update `index.md`, `current-state.md`, and `indexes/*` so agents can retrieve the right memory quickly.
4. Stale, weak, or contradictory evidence stays marked with dates and compact source references.

## Core Sections

- `company/` - what the company does, business context, priorities, values, terminology, and operating model.
- `team/` - work-relevant people, teams, ownership, decision rights, collaboration patterns, and preferences.
- `tools/` - tools and systems the company uses, what they are for, and important usage patterns.
- `customers/` - customer organizations, personas, feedback themes, commitments, and needs.
- `projects/` - active and historical initiatives, status, owners, blockers, and next steps.
- `decisions/` - durable decisions with context, rationale, dates, owners, and supersession links.
- `architecture/` - technical systems, repos, services, data flows, constraints, and design tradeoffs.
- `product/` - roadmap, product areas, feature behavior, positioning, and feedback.
- `processes/` - recurring workflows, rituals, policies, playbooks, and handoffs.
- `risks/` - known risks, incidents, mitigations, and watch items.
- `questions/` - open questions that need validation or owner input.
- `entities/` - broad cross-reference pages for people, teams, customers, vendors, tools, products, repos, and systems.
- `sources/` - source connector registry, capability maps, container ledgers, and ingestion coverage.
- `summaries/` - synthesized briefings that point to curated pages.
- `archive/` - superseded or historical pages kept for traceability.

## Curated Page Frontmatter

Use compact frontmatter when known:

- `title`
- `type`
- `status`
- `confidence`
- `created`
- `updated`
- `last_verified`
- `review_after`
- `owners`
- `platforms`
- `entities`
- `tags`
- `source_refs`
- `supersedes`
- `superseded_by`

## Evidence Rules

- Prefer updating existing pages over creating duplicates.
- Do not paste raw provider payloads, full threads, email bodies, long document excerpts, secrets, preview URLs, `.env`, `auth.json`, bearer tokens, or sensitive personal data.
- People memory must be work-relevant, sourced, useful, and respectful. Do not store protected traits, compensation, gossip, psychological labels, private personal details, or performance criticism.
- Use compact source references instead of long excerpts.
- Preserve uncertainty and contradictions with dates and source references.
""",
        "index.md": f"""---
title: Company Memory Wiki Index
type: index
status: active
confidence: medium
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, retrieval]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Wiki Index

Use this as the primary retrieval surface for the Company Memory company-memory wiki.

## Start Here

- [Current State](current-state.md)
- [Schema](SCHEMA.md)
- [Agent Map](indexes/agent-map.md)
- [By Source](indexes/by-source.md)
- [By Entity](indexes/by-entity.md)
- [Stale And Contested](indexes/stale-and-contested.md)
- [Open Questions](indexes/open-questions.md)

## Company Memory

- `company/` - company context, priorities, values, terminology, and operating model.
- `team/` - people, teams, ownership, decision rights, collaboration patterns, and preferences.
- `tools/` - tools and systems in use and how work flows through them.
- `customers/` - customers, segments, feedback, commitments, and needs.
- `projects/` - initiatives, owners, state, blockers, and next actions.
- `decisions/` - durable decisions, rationale, and supersession history.
- `architecture/` - technical systems and design context.
- `product/` - product areas, roadmap, behavior, and positioning.
- `processes/` - workflows, rituals, policies, and playbooks.
- `risks/` - risks, incidents, mitigations, and watch items.
- `questions/` - unresolved questions.
- `entities/` - cross-reference pages for people, teams, customers, tools, products, repos, and systems.

## Source Memory

- [Source Registry](sources/source-registry.md)
- `raw/session-summaries/` - low-confidence session summary receipts.
- `raw/runs/` - low-confidence source crawl receipts.
- `raw/_state/` - cursors, policies, and crawl state.
""",
        "current-state.md": f"""---
title: Company Memory Current State
type: current_state
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, current-state]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Current State

The wiki has been initialized, but no curated company state has been promoted yet.

## Company

- Unknown.

## Team

- Unknown.

## Customers

- Unknown.

## Product And Projects

- Unknown.

## Tools And Systems

- Unknown.

## Decisions

- Unknown.

## Risks And Open Questions

- See [Open Questions](indexes/open-questions.md) and [Stale And Contested](indexes/stale-and-contested.md).
""",
        "indexes/agent-map.md": f"""---
title: Company Memory Agent Map
type: index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, agent-map]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Agent Map

Map common user questions to the wiki pages that should answer them.

## Routes

- Company overview -> `company/`, `current-state.md`
- People, teams, owners, collaboration -> `team/`, `entities/`, `indexes/by-entity.md`
- Tools and systems -> `tools/`, `sources/`, `architecture/`
- Customers and feedback -> `customers/`, `product/`
- Active work -> `projects/`, `current-state.md`
- Decisions -> `decisions/`
- Risks and stale assumptions -> `risks/`, `indexes/stale-and-contested.md`
""",
        "indexes/by-source.md": f"""---
title: Company Memory By Source Index
type: index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, sources]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory By Source Index

Track source connectors, source containers, ingestion coverage, and the curated pages they support.

## Sources

- See [Source Registry](../sources/source-registry.md).
""",
        "indexes/by-entity.md": f"""---
title: Company Memory By Entity Index
type: index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, entities]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory By Entity Index

Track important people, teams, customers, tools, vendors, products, repos, and systems.

## People And Teams

- Curated work-relevant pages belong in `team/`; cross-reference entries may also live in `entities/`.

## Customers

- Curated customer pages belong in `customers/`; cross-reference entries may also live in `entities/`.

## Tools And Systems

- Curated tool pages belong in `tools/` or `architecture/`; cross-reference entries may also live in `entities/`.
""",
        "indexes/stale-and-contested.md": f"""---
title: Company Memory Stale And Contested Index
type: index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, stale, contested]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Stale And Contested Index

Track stale assumptions, contradictions, weak evidence, and pages that need re-verification.

## Items

- None recorded.
""",
        "indexes/open-questions.md": f"""---
title: Company Memory Open Questions Index
type: index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, open-questions]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Open Questions Index

Track questions that need source validation or owner input.

## Questions

- None recorded.
""",
        "sources/source-registry.md": f"""---
title: Company Memory Source Registry
type: source_registry
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, sources]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Source Registry

Track connected source toolkits, capability maps, container ledgers, ingestion state, and safe source references.

## Connected Toolkits

- Unknown.
""",
        "company/README.md": section_readme(
            date,
            "Company",
            "what the company does, business context, priorities, values, terminology, and operating model",
        ),
        "team/README.md": f"""---
title: Company Memory Team Memory
type: section_index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, team]
source_refs: []
supersedes: []
superseded_by: []
---

# Team

Use this section for work-relevant people and team memory: roles, ownership, decision rights, collaboration patterns, communication preferences, and recurring working relationships.

Do not store private personal details, protected traits, compensation, gossip, psychological labels, or performance criticism.
""",
        "tools/README.md": section_readme(
            date,
            "Tools",
            "tools and systems the company uses, what each tool is for, important containers, conventions, and work patterns",
        ),
        "entities/README.md": f"""---
title: Company Memory Entities
type: section_index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, entities]
source_refs: []
supersedes: []
superseded_by: []
---

# Entities

Use this section for broad cross-reference pages spanning people, teams, customers, vendors, tools, products, repos, and systems.

Prefer first-class sections for curated substance:

- People and working relationships -> `team/`
- Customer memory -> `customers/`
- Tool usage -> `tools/`
- Technical systems -> `architecture/`
""",
        "logs/wiki-changes.md": f"""---
title: Company Memory Wiki Changes
type: change_log
status: active
confidence: high
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, changelog]
source_refs: []
supersedes: []
superseded_by: []
---

# Company Memory Wiki Changes

## {date}

- Initialized default company-memory wiki structure at {timestamp}.
""",
    }


def section_readme(date: str, title: str, purpose: str) -> str:
    slug = title.lower().replace(" ", "-")

    return f"""---
title: Company Memory {title}
type: section_index
status: active
confidence: low
created: {date}
updated: {date}
last_verified: {date}
review_after:
owners: []
platforms: []
entities: []
tags: [company-memory, {slug}]
source_refs: []
supersedes: []
superseded_by: []
---

# {title}

Use this section for {purpose}.
"""


def atomic_write_text(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(target.parent),
        prefix=f".{target.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        temp_name = handle.name

    Path(temp_name).replace(target)
