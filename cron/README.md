# Hermes Scheduler

Phoenix does not run a host cron tick for Hermes. Scheduler definitions that should run inside the Hermes gateway belong in this directory.

`jobs.json` is the profile-owned Hermes cron store. Hermes gateway reads that file from the active profile home and computes `next_run_at` when the scheduler ticks. Keep `next_run_at` nullable in checked-in recurring jobs so each installed sandbox schedules the first future run for itself.

The Markdown files in this directory are human-readable prompt copies for review. If a cron prompt changes, update the matching `prompt` field in `jobs.json`.

Shipped jobs:

- `slack-people-profile-producer`: runs every 12 hours, scans Slack users, reconciles completed/active `slack.person_profile` Kanban tasks, updates `/opt/data/phoenix/crawl-state/people-crawl.json`, and enqueues bootstrap or 7-day refresh tasks.

Reusable task templates:

- `phoenix-ingestion-task-contract.md`: general producer/worker contract for Kanban-backed ingestion work such as `slack.person_profile`, `slack.channel_summary`, and `slack.thread_summary`.
- `people-profile-crawl.md`: task body template for a `slack.person_profile` Kanban worker. This file is not scheduled as a cron job. Workers return one Markdown report and complete the card with that report as the Kanban result.

The Phoenix Hermes image wrapper owns profile install/update, Composio CLI and
nori-slack CLI availability, OpenViking startup, `nori-slack-cli` skill
verification, and creation of the shared `phoenix-ingestion` board. Producer
prompts assume that setup has already completed and should not create boards
themselves.
