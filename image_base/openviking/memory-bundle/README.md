# OpenViking Company Memory Bundle

This bundle configures OpenViking with dedicated company-memory schemas. The
Hermes provider can be general-purpose, but these OpenViking extraction schemas
remain company-specific.

## Design Stance

- OpenViking stores durable company memory in the custom schema set.
- Hermes built-in memory can still hold local/user operating preferences.
- The OpenViking memory tree itself is the durable company memory surface.
- Predefined schemas provide structure.
- `company_page` / `pages/` provides the controlled flexible page area.
- Built-in `profile`, `preferences`, and `entities` are disabled; built-in `events` remains enabled.
- All predefined schemas include freestyle escape hatches:
  - `custom_properties`
  - `custom_sections`
  - `evidence`

## Directory Layout

```text
config/
  ov.memory.example.jsonc

custom-memory/
  profile.yaml
  preferences.yaml
  entities.yaml
  company_profile.yaml
  company_person.yaml
  company_team.yaml
  company_project.yaml
  company_decision.yaml
  company_page.yaml

examples/
  expected_memory_tree.md
  ingestion_source_wrappers.md
  example_company_memory.md

tests/
  smoke_queries.md
  sample_extraction_input.md

scripts/
  validate_yaml.py

docs/
  implementation_notes.md
```

## Intended OpenViking Memory Tree

```text
viking://user/<user_space>/memories/
├── profile.md
├── people/
├── teams/
├── projects/
├── decisions/
└── pages/
```

Resources remain under:

```text
viking://resources/
```

## Install Sketch

1. Copy `custom-memory/` somewhere stable, for example:

```bash
/srv/phoenix/openviking/company-memory
```

2. Adapt `config/ov.memory.example.jsonc` into your OpenViking `ov.conf`.
3. Validate YAML syntax:

```bash
python scripts/validate_yaml.py
```

4. Run a small extraction test with `tests/sample_extraction_input.md`.

## Memory Types

- `company_profile`: one company-level profile page.
- `company_person`: people, roles, ownership, decision rights, and org-chart-relevant facts.
- `company_team`: teams, charters, leads, members, responsibilities, rituals, and owned assets.
- `company_project`: active/paused/archived initiatives and programs.
- `company_decision`: durable decisions with date, owner, status, rationale, consequences, and supersession.
- `company_page`: flexible Markdown page for durable company knowledge that does not fit stricter schemas.
