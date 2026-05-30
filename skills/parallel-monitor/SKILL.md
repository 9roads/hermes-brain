---
name: parallel-monitor
description: Create and manage Parallel web monitors that track recurring web changes and events.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [phoenix, parallel, web, monitor, cli]
    requires_toolsets: [terminal]
---

# Parallel Monitor

Use this skill when the user asks to monitor, watch, track, or alert on web
changes over time. Monitors are long-running server-side jobs. Phoenix provides
`parallel-cli` and `PARALLEL_API_KEY` at runtime. Do not print, paste, persist,
echo, or include the API key in command output, logs, reports, or final
responses.

## Decide The Action

| Intent | Action |
| --- | --- |
| "Track / watch / monitor / alert me when X" | create |
| "What am I monitoring?" / "List monitors" | list |
| "What changed?" / "Show events for monitor X" | events |
| "Show monitor X" / "Get details for X" | get |
| "Change cadence / query / webhook for X" | update |
| "Test the webhook" / "Fire a test event" | simulate |
| "Show the full payload for event group X" | event-group |
| "Stop / delete monitor X" | delete, after explicit confirmation |

## Create

```bash
parallel-cli monitor create "<query>" --cadence daily --json
```

Cadence options are `hourly`, `daily`, `weekly`, and `every_two_weeks`. Match
cadence to signal velocity: hourly for prices/news, weekly for slower filings
or staffing pages.

Useful options:

- `--webhook https://example.com/hook` to deliver events.
- `--metadata '{"team":"competitive-intel"}'` for bookkeeping.
- `--output-schema '<json>'` for structured event payloads.

Parse the JSON for `monitor_id`. Tell the user the ID, cadence, and how to view
events later.

## List

```bash
parallel-cli monitor list -n 10 --json
```

Default to `-n 10` so old monitor history does not flood context. Present ID,
query, cadence, and creation time as a compact table.

## Events

```bash
parallel-cli monitor events "$MONITOR_ID" --lookback 10d --json
```

Lookback format is `Nd` for days or `Nw` for weeks. Default to `10d`.

For deeper detail:

```bash
parallel-cli monitor event-group "$MONITOR_ID" "$EVENT_GROUP_ID" --json
```

Summarize event counts, timestamps, what changed, and source URLs from the event
payload.

## Get / Update / Delete

```bash
parallel-cli monitor get "$MONITOR_ID" --json
parallel-cli monitor update "$MONITOR_ID" --cadence weekly --json
parallel-cli monitor delete "$MONITOR_ID" --json
```

Deletion is permanent. Always get explicit confirmation before deleting a
monitor.
