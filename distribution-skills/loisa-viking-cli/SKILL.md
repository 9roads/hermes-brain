---
name: loisa-viking-cli
description: Use the OpenViking CLI to search, browse, read, ingest, and capture Loisa company memory and resources.
version: 0.1.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [loisa, openviking, memory, cli]
    requires_toolsets: [terminal]
---

# Loisa Viking CLI

Use this skill when you need to inspect or update Loisa's OpenViking-backed
company memory and resources from the shell.

Loisa installs OpenViking in the Hermes image and exposes both `ov` and
`openviking` on `PATH`. Prefer the short `ov` command. Use `openviking` only if
`ov` is unavailable.

Dont output full paths to resources and memories. Just output simple things like "Added content to resources" etc and only if explicitly asked for path output without viking:// prefix. Prefer short, human-friendly messages over raw CLI output.

## Configuration

The runtime sets OpenViking connection details before Hermes starts:

- `OPENVIKING_CLI_CONFIG_FILE` points to `ovcli.conf`.
- `OPENVIKING_USER_SPACE` is the current OpenViking user namespace.
- `OPENVIKING_AGENT_ID` is the OpenViking agent provenance id.

Use JSON output for structured reads:

```bash
ov -o json ls viking://resources
openviking -o json ls viking://resources
```

Some content commands, such as `read`, `abstract`, and `overview`, may print
plain text even when JSON output is requested.

## Search Policy

Never search `viking://session` for ordinary memory lookup. Session archives are
internal provenance, not the default knowledge source.

Default search scopes:

```text
viking://resources
viking://user/${OPENVIKING_USER_SPACE:-default}/memories
```

Search resources and user memories separately when you need full coverage:

```bash
ov -o json search "deployment decision" --uri viking://resources --limit 8
ov -o json search "deployment decision" --uri "viking://user/${OPENVIKING_USER_SPACE:-default}/memories" --limit 8
```

Use `search` for conversational or intent-aware retrieval. Use `find` for a
direct semantic lookup when you know the query is already specific:

```bash
ov -o json find "OAuth login recommendation" --uri viking://resources --limit 10
ov -o json find "user preference about deploys" --uri "viking://user/${OPENVIKING_USER_SPACE:-default}/memories" --limit 10
```

## Browse And Read

List directories when you know the area to inspect:

```bash
ov -o json ls viking://resources
ov -o json ls "viking://user/${OPENVIKING_USER_SPACE:-default}/memories"
```

Load context progressively. Start with abstracts or overviews, then read full
content only when exact details matter:

```bash
ov abstract viking://resources/docs
ov overview viking://resources/docs
ov read viking://resources/docs/runbook.md
```

Use exact text and glob searches for identifiers, quoted strings, filenames, or
paths:

```bash
ov -o json grep viking://resources "customer_id" --ignore-case
ov -o json grep "viking://user/${OPENVIKING_USER_SPACE:-default}/memories" "launch plan"
ov -o json glob "**/*.md" --uri viking://resources
```

## Add Resources

Use `add-resource` for public URLs, Git URLs, bounded local files, or bounded
local directories. The CLI automatically handles local file and directory
uploads before calling the OpenViking server.

```bash
ov add-resource https://example.com/guide.md --to viking://resources/external/guide.md --reason "Reusable guide"
ov add-resource ./docs/runbook.md --parent viking://resources/docs --reason "Project runbook"
ov add-resource ./exported-thread --parent viking://resources/slack --reason "Bounded exported source material"
```

For remote resources that should refresh, use a target URI and watch interval:

```bash
ov add-resource https://github.com/example/repo.git --to viking://resources/repos/example --watch-interval 60
```

## Capture Durable Memory

Use explicit memory capture only when the user asks to remember something or the
fact is high-confidence, durable company context. Prefer short, source-grounded
messages.

```bash
ov add-memory '[{"role":"user","content":"Remember that Loisa deploy reviews happen before customer-facing runtime changes."}]'
```

Do not capture transient chat, speculation, raw transcripts, long excerpts,
secrets, credentials, .env contents, private personal details, protected traits,
compensation, gossip, psychological labels, performance criticism, or unbounded
provider dumps.

## Output And Errors

Prefer `-o json` for commands that return structured data. If a command fails,
read the JSON error or stderr message, adjust the command, and retry only when
the fix is clear.

Do not print tokens, API keys, config contents, or raw private payloads in user
responses.
