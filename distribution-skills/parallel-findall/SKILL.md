---
name: parallel-findall
description: Discover entities matching a natural-language description, such as companies, people, products, or organizations.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [loisa, parallel, web, findall, entity-discovery, cli]
    requires_toolsets: [terminal]
---

# Parallel FindAll

Use this skill when the user wants a structured list of entities matching a
description, not webpages or a narrative answer. Loisa provides
authenticated `parallel-cli` at runtime. Do not inspect, print, paste, persist,
echo, or include Parallel credentials in command output, logs, reports, or
final responses.

## When To Use

| User asks for                                 | Use                      |
| --------------------------------------------- | ------------------------ |
| "Find all X that..." / "List every Y..."      | `parallel-findall`       |
| Webpage results, quick answers, current facts | `parallel-web-search`    |
| Narrative reports or deep analysis            | `parallel-deep-research` |

Keep in mind that findall is powerful but expensive and can take a while to complete. Do not run multiple findall runs in sequence or in parallel. Prefer at most one findall run per session.

## Step 1 - Start The Run

```bash
parallel-cli findall run "$ARGUMENTS" --no-wait --json
```

Defaults are generator `core` and match limit `10`. `core` should be used only for less then 30 matches. Prefer `base` for most broader queries. `pro` is expensive and slower. Use it very rarely for comprehensive coverage or sparse matches.

- `-n 50` raises the match limit; valid range is 5-1000.

If the user wants to exclude known entities:

```bash
parallel-cli findall run "$ARGUMENTS" --no-wait --json --exclude '[{"name":"Google","url":"google.com"},{"name":"OpenAI","url":"openai.com"}]'
```

If the objective is ambiguous, preview the inferred entity type and match
conditions:

```bash
parallel-cli findall ingest "$ARGUMENTS" --json
```

Parse the JSON for `findall_id` and any monitoring URL. Tell the user the run
started and that it may take a few minutes.

## Step 2 - Poll For Results

Choose a descriptive filename, using lowercase words with hyphens and no spaces.

```bash
parallel-cli findall poll "$FINDALL_ID" -o "/tmp/<filename>.json" --timeout 540
```

Do not pass `--json` for large result sets; save the full results to disk.

If polling times out, the server-side run can still be running. Re-run the same
poll command to continue waiting.
