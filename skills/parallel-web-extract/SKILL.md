---
name: parallel-web-extract
description: Extract clean content from public URLs, articles, PDFs, and JavaScript-heavy pages with Parallel CLI.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [phoenix, parallel, web, extract, cli]
    requires_toolsets: [terminal]
---

# Parallel URL Extraction

Use this skill when the user provides a URL or when search has already narrowed
the sources to read. Phoenix provides `parallel-cli` and `PARALLEL_API_KEY` at
runtime. Do not print, paste, persist, echo, or include the API key in command
output, logs, reports, or final responses.

## Command

Choose a short, descriptive filename based on the URL or content, using
lowercase words with hyphens and no spaces. The output extension must be
`.json`.

```bash
parallel-cli extract "$ARGUMENTS" --json -o "/tmp/<filename>.json"
```

Concrete example:

```bash
parallel-cli extract "https://docs.parallel.ai" --json -o "/tmp/parallel-docs.json"
```

Useful options:

- `--objective "focus area"` to focus extraction on a specific goal.
- `-q "keyword"` to prioritize keywords; repeat as needed.
- `--full-content` to include the complete page body.
- `--full-content-max-chars N` to cap full content.
- `--no-excerpts` when only full content is useful.

## Response Format

Return extracted content as:

```text
**[Page Title](URL)**

<extracted content>
```

Preserve facts, names, dates, numbers, quotes, and list structure. Strip only
obvious page noise such as navigation, ads, cookie banners, and footers. Mention
the saved output path so follow-up work can reuse it.
