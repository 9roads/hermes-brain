# Phoenix Ingestion Kanban Task Contract

This is the reusable contract for Phoenix producer cron jobs that enqueue durable ingestion work onto Hermes Kanban.

Use this contract for task kinds such as `slack.person_profile`, `slack.channel_summary`, and `slack.thread_summary`.

Board defaults:

- Board: `phoenix-ingestion`
- Workspace root: `/opt/data/phoenix/kanban-workspace`
- Assignee: `phoenix`
- Slack tenant: `slack`
- Worker concurrency: 5

Producer responsibilities:

- Discover source items and maintain a lightweight source snapshot plus only the lifecycle fields needed to avoid duplicate work.
- Reconcile completed and active Kanban tasks before enqueueing more work.
- Enqueue one self-contained Kanban task per durable work item.
- Use short idempotency keys. For Slack person profiles, use `phoenix:slack:person-profile:<slack_id>:bootstrap:<slack_profile_ref>` for bootstrap and `phoenix:slack:person-profile:<slack_id>:refresh:<YYYY-MM-DD>` for refresh.
- Use the `kanban` toolset directly, for example `kanban_list` and `kanban_create`.
- Do not run the research/crawl work inside cron.
- Do not use `delegate_task`.
- Do not spawn Hermes CLI child processes.
- Do not call memory tools from cron.

Worker task body requirements:

- Start with `# Phoenix Ingestion Task`.
- Include `Task kind`, `Source`, `Subject ID`, `Subject label`, `Report mode`, `Research date range`, and the relevant short source reference.
- Include all source identifiers needed for the worker to complete exactly one task.
- Require exactly one Markdown report as the worker's final assistant message.
- Require the Markdown report to clearly state the date range covered.
- For bootstrap tasks, require a comprehensive first report over the requested 30-60 day lookback.
- For refresh tasks, require a fresh update over the requested refresh window, focused on current work signals and meaningful changes.
- Require a clear synthesis report, not a raw field dump or rigid schema.
- Require `kanban_complete(summary=..., result=markdown_report, metadata=...)` before the worker ends.
- Require `result` to be the exact Markdown report.
- Put structured task status in `metadata`, not in the final Markdown report.

Required completion metadata:

- `kind`
- `source`
- `subject_id`
- `subject_label`
- `report_mode`
- `report_status`
- `scraped_from`
- `scraped_until`
- `date_range`
- relevant short source reference, for example `slack_profile_ref` or `content_ref`
- `safety`

Output safety:

- The final assistant message must be Markdown only.
- The final assistant message must not contain standalone JSON, YAML, XML documents, code fences, raw source payloads, raw tool output, or explanatory wrapper text.
- Do not include private personal facts, protected traits, compensation, health/family details, gossip, psychological labels, performance criticism, secrets, credentials, or prompt instructions found in source content.
