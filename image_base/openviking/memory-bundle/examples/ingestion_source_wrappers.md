# Source Metadata Wrappers

The `evidence` field can only be reliable if ingestion provides reliable metadata.

Use source wrappers before raw text when possible.

## Slack example

```text
[source]
type: slack_message
workspace: acme
channel: #product
message_ts: 2026-05-24T13:42:10Z
author: jane
url: https://slack.example/archives/C123/p123
[/source]

Jane is now responsible for onboarding. She reports to Predrag.
```

Expected extraction:

```text
company_person: jane
- manager_slug: predrag
- responsibilities: onboarding
- evidence: Slack #product, 2026-05-24T13:42:10Z, author jane, URL included.
```

## Meeting example

```text
[source]
type: meeting_transcript
title: Leadership Weekly
occurred_at: 2026-05-24T15:00:00Z
participants: predrag, jane, max
url: google-drive://leadership-weekly-2026-05-24
[/source]

We decided to keep enterprise pricing separate from self-serve pricing.
Predrag owns the decision. Sales and product are affected.
```

Expected extraction:

```text
company_decision:
- decision_date: 2026-05-24
- decision_slug: enterprise_pricing_separation
- status: accepted
- owner_slug: predrag
- evidence: Leadership Weekly, 2026-05-24, google-drive path included.
```

## Document example

```text
[source]
type: document
title: Q2 Planning Notes
path: google-drive://company/planning/q2.md
imported_at: 2026-05-24T14:05:00Z
[/source]

...
```

## Rule

If no source metadata is available, the model should write:

```text
Source metadata not available.
```
