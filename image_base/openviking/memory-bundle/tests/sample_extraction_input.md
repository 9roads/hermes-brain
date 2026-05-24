# Sample Extraction Input

Use this text in a test session and inspect the generated memories.

```text
[source]
type: meeting_transcript
title: Loisa Architecture Review
occurred_at: 2026-05-24T15:00:00Z
participants: predrag, jane, max
url: google-drive://loisa/meetings/2026-05-24-architecture-review
[/source]

Loisa is a company brain agent based on Hermes. We decided that OpenViking should be used purely for company memory.
Hermes should keep user preferences, assistant behavior preferences, tool behavior, and local profile behavior.

We decided the flexible company-memory area should be named pages, not cards.
The predefined OpenViking company memory schemas are company_profile, company_person, company_team, company_project, company_decision, and company_page.
Built-in events remain enabled for dated event and session history.

Jane owns onboarding and reports to Predrag. Do not infer any other reporting lines.
Max is helping with the referral project, but he is not necessarily a permanent member of the Growth team.

The main risk is memory pollution: OpenViking should not accidentally store personal assistant preferences or tool usage memories.
```

Expected memory types:

- company_profile
- company_person
- company_project
- company_decision
- company_page
- events

Unexpected memory types:

- profile
- preferences
- tools
- skills
- entities
- cases
- patterns
```
