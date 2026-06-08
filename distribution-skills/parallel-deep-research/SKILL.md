---
name: parallel-deep-research
description: Use Parallel Task/deep research only when the user explicitly asks for deep research, exhaustive investigation, a comprehensive report, or multi-source analysis.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [loisa, parallel, web, task, research, cli]
    requires_toolsets: [terminal]
---

# Parallel Task / Deep Research

Use this skill for Parallel Task-style deep research. It is slower and more
expensive than `parallel-web-search`; use search for normal lookup,
fact-checking, and lightweight research. Loisa provides authenticated
`parallel-cli` at runtime. Do not inspect, print, paste, persist, echo, or
include Parallel credentials in command output, logs, reports, or final
responses.

## When To Use

Use this skill when the user explicitly asks for deep research, exhaustive
coverage, a comprehensive report, or a thorough investigation that needs
synthesis across many sources.

Keep in mind that research is powerful but expensive and can take a while to complete. Do not run multiple research tasks in sequence or in parallel. Prefer at most one research task per session.

## Step 1 - Start The Task

Choose a descriptive filename based on the topic, using lowercase words with
hyphens and no spaces. Reuse this base name when polling.

```bash
parallel-cli research run "$ARGUMENTS" --processor pro-fast --text --no-wait --json
```

Use `--text` for narrative/report-style requests so the completed task writes a
markdown report with citations. Drop `--text` only when the user explicitly
wants structured JSON output.

Optional steering:

```bash
parallel-cli research run "$ARGUMENTS" --processor pro-fast --text --text-description "Keep under 1500 words and focus on M&A activity" --no-wait --json
```

For a follow-up where you know the previous `interaction_id`, chain context:

```bash
parallel-cli research run "$ARGUMENTS" --processor lite-fast --text --no-wait --json --previous-interaction-id "$INTERACTION_ID"
```

Processor defaults:

| Processor                                        | Expected latency | Use when                    |
| ------------------------------------------------ | ---------------- | --------------------------- |
| `lite-fast`                                      | 10-60s           | Quick follow-ups            |
| `base-fast`                                      | 15-100s          | Simple questions            |
| `core-fast`                                      | 1-5 min          | Moderate research           |
| `pro-fast`                                       | 2-10 min         | Default depth/speed balance |
| `ultra-fast`                                     | 5-25 min         | Multi-source deep research  |
| `ultra2x-fast` / `ultra4x-fast` / `ultra8x-fast` | up to 2 hr       | Hardest explicit requests   |

Default to `-fast` processors unless the user asks about news from the last day
or two, where non-fast processors may fetch fresher data.

Parse the JSON output for `run_id`, `interaction_id`, and the monitoring URL.
Tell the user the task started, the expected latency, and the monitoring URL.

## Step 2 - Poll For Results

```bash
parallel-cli research poll "$RUN_ID" -o "/tmp/<filename>" --timeout 540
```

Do not pass `--json` to polling unless the user specifically needs raw JSON in
stdout. With `-o`, Parallel writes `/tmp/<filename>.json`, and also
`/tmp/<filename>.md` when the task was started with `--text`.

If polling times out, the server-side task can still be running. Re-run the same
poll command to continue waiting.

## Response Format

After the task starts, share the monitoring URL. After polling completes, share
the executive summary printed by the command, the generated file paths, and the
`interaction_id` for future follow-up questions.
