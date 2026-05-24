# Hermes Scheduler

Phoenix does not run a host cron tick for Hermes. Scheduler definitions that should run inside the Hermes gateway belong in this directory.

`jobs.json` is the profile-owned Hermes cron store. Hermes gateway reads that file from the active profile home and computes `next_run_at` when the scheduler ticks. Keep `next_run_at` nullable in checked-in recurring jobs so each installed sandbox schedules the first future run for itself.

The Markdown files in this directory are human-readable prompt copies for review. If a cron prompt changes, update the matching `prompt` field in `jobs.json`.

No default scheduled jobs are currently shipped. Durable company context flows through the OpenViking memory provider and its model tools.
