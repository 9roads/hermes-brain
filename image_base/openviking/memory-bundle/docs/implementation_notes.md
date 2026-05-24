# Implementation Notes

## Company Schemas Stay Dedicated

The Hermes provider is named `openviking_memory` and exposes general `memory_*`
tools, but this bundle intentionally keeps the dedicated company memory schemas.
OpenViking extraction should continue to target:

```text
company_profile
company_person
company_team
company_project
company_decision
company_page
```

Built-in `profile`, `preferences`, and `entities` are disabled by replacement
schemas because this OpenViking configuration is still the company-memory
surface.

## Flexible Pages

Use `company_page.section_slug` and `company_page.page_slug` as the controlled
dynamic page path:

```text
pages/operations/onboarding.md
pages/sales/enterprise_pricing.md
pages/customers/acme_corp.md
pages/engineering/hermes_boundary.md
pages/glossary/loisa.md
pages/risks/memory_pollution.md
```

Default top-level page sections:

```text
strategy
product
customers
sales
marketing
operations
engineering
finance
legal
hiring
glossary
risks
vendors
metrics
raw_notes
```

New top-level sections are allowed only when none of the defaults fit cleanly.
Page slugs must not contain slashes.

## Evidence

Use only source metadata present in the input. Do not fabricate exact sources.
When exact source data is absent, write that source metadata is not available.

## Org Chart

No stored generated org-chart page is required. Generate the org chart at query
time from people and team memories. Do not infer missing reporting lines.
