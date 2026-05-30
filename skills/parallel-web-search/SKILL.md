---
name: parallel-web-search
description: DEFAULT for public web search, current facts, lookup, fact-checking, and lightweight research. Use parallel-deep-research only for explicit deep or exhaustive research requests.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [phoenix, parallel, web, search, cli]
    requires_toolsets: [terminal]
---

# Parallel Web Search

Use this skill for public web search and current-information lookup. Phoenix
provides `parallel-cli` and `PARALLEL_API_KEY` at runtime. Do not print, paste,
persist, echo, or include the API key in command output, logs, reports, or final
responses.

## Command

Choose a short, descriptive filename based on the query, using lowercase words
with hyphens and no spaces. Substitute it directly in the command.

```bash
parallel-cli search "$ARGUMENTS" -q "<keyword1>" -q "<keyword2>" --json --max-results 10 -o "/tmp/<filename>.json"
```

Concrete example:

```bash
parallel-cli search "latest React 19 features and adoption" -q "React 19" -q "concurrent rendering" --json --max-results 10 -o "/tmp/react-19-features.json"
```

The first argument is the objective: a natural-language description of what you
are looking for. Add `-q` flags for specific keyword queries that supplement the
objective. Prefer one good Parallel call over several traditional keyword
searches.

Useful options:

- `--after-date YYYY-MM-DD` for time-sensitive queries.
- `--include-domains domain1.com,domain2.com` to limit sources.
- `--exclude-domains domain.com` to filter noisy sources.
- `--mode agentic` for harder multi-step search; default behavior is right for
  most searches.
- `--location us` for geo-targeted results.

## Parsing Results

Prefer the saved `-o` file over stdout. Read `/tmp/<filename>.json` as the
authoritative payload. For each useful result, extract title, URL, publish date
when present, and substantive excerpts. Skip navigation, cookie banners,
footers, and other page chrome.
