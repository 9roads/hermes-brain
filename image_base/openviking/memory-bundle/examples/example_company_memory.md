# Example Company Memory Output

Input:

```text
[source]
type: slack_message
workspace: loisa
channel: #leadership
message_ts: 2026-05-24T13:42:10Z
author: predrag
[/source]

Loisa should use OpenViking for durable company memory. The flexible company
memory area should be called pages, not cards. Jane owns onboarding and reports
to Predrag.
```

Expected memory candidates:

## company_profile

```text
company_name: Loisa
products_services: Company brain agent based on Hermes, with OpenViking-backed company memory.
custom_properties:
  memory_boundary:
    value: OpenViking stores durable company memory.
    confidence: high
    evidence: Slack #leadership, 2026-05-24T13:42:10Z, author predrag.
evidence: Slack #leadership, 2026-05-24T13:42:10Z, author predrag.
```

## company_decision

```text
decision_date: 2026-05-24
decision_slug: flexible_memory_area_named_pages
title: Flexible memory area named pages
status: accepted
owner_slug: predrag
decision: The flexible company-memory area should be named pages, not cards.
evidence: Slack #leadership, 2026-05-24T13:42:10Z, author predrag.
```

## company_person

```text
person_slug: jane
full_name: Jane
manager_slug: predrag
responsibilities: Owns onboarding.
evidence: Slack #leadership, 2026-05-24T13:42:10Z, author predrag.
```

## company_page

```text
section_slug: engineering
page_slug: hermes_boundary
title: Hermes and OpenViking memory boundary
page_type: system
summary: Durable company memory is extracted into OpenViking company schemas.
evidence: Slack #leadership, 2026-05-24T13:42:10Z, author predrag.
```
