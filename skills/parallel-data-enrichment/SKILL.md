---
name: parallel-data-enrichment
description: Bulk enrich CSV files or inline lists with web-sourced fields such as CEO names, funding, contact info, or product metadata.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [phoenix, parallel, web, enrichment, cli]
    requires_toolsets: [terminal]
---

# Parallel Data Enrichment

Use this skill when the user wants to add web-sourced columns to a list of
companies, people, products, or other entities. Phoenix provides authenticated
`parallel-cli` at runtime. Do not inspect, print, paste, persist, echo, or
include Parallel credentials in command output, logs, reports, or final
responses.

## Before Starting

Tell the user that enrichment can take several minutes depending on row count
and requested fields. Prefer a small, explicit enrichment intent when the user
has already specified the fields they want.

## Optional Column Suggestion

If the user gave a vague request such as "enrich these companies with useful
info", ask Parallel for suggested output columns before starting the run:

```bash
parallel-cli enrich suggest "$ARGUMENTS" --json
```

The response is an envelope containing `title`, `processor`,
`enriched_columns`, and `warnings`. Pass only the `enriched_columns` array to
`--enriched-columns` on `enrich run`; do not combine `--enriched-columns` with
`--intent`. If `suggest` returns a `processor`, pass it through explicitly on
the run command.

Skip this step when the user already named the fields to add.

## Step 1 - Start The Enrichment

Use exactly one source pattern.

For inline data:

```bash
parallel-cli enrich run --data '[{"company":"Google"},{"company":"Microsoft"}]' --intent "CEO name and founding year" --target "output.csv" --no-wait --json
```

For a CSV file:

```bash
parallel-cli enrich run --source-type csv --source "input.csv" --target "output.csv" --source-columns '[{"name":"company","description":"Company name"}]' --intent "CEO name and founding year" --no-wait --json
```

For a follow-up to a previous Parallel deep research task, add context chaining
when you have the prior `interaction_id`:

```bash
parallel-cli enrich run --data '...' --intent "..." --target "output.csv" --no-wait --json --previous-interaction-id "$INTERACTION_ID"
```

Always include `--no-wait` so the command returns immediately. Parse the JSON
for `taskgroup_id`, `url`, and `num_runs`. There is no `interaction_id` in
enrichment output.

After starting, tell the user the enrichment has started, share the monitoring
URL, and note that polling can run in the background while other work continues.

## Step 2 - Poll For Results

Choose a descriptive JSON path. The completed file is a JSON array of
`{input, output}` objects, even when the start command used a CSV target.

```bash
parallel-cli enrich poll "$TASKGROUP_ID" --timeout 540 --output "/tmp/enrichment-<descriptive-name>.json"
```

Use `--timeout 540` to stay within normal command limits. In `--no-wait` mode,
the `--target` from step 1 is not the completed result file; the `--output`
path on the poll command is what saves the JSON results.

If polling times out, the server-side enrichment can still be running. Re-run
the same poll command to continue waiting.
