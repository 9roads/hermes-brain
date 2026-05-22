---
name: composio-cli
description: Use the Composio CLI to search, execute, and proxy tools inside Phoenix-injected Tool Router sessions.
---

# Composio CLI Usage Guide

Use `composio` to operate on the existing Composio Tool Router session that Phoenix injects for the current Hermes session. The CLI can search for tools, execute tool slugs, and proxy provider API requests through connected accounts in that session.

Phoenix passes the project-scoped Composio key as `COMPOSIO_API_KEY`. Do not print, paste, or persist it.

## Session ID

Every command requires the injected Tool Router session id. Find it in the system prompt block headed exactly:

```text
Composio Tool Router session:
```

Read the value from that block's `COMPOSIO_TOOL_ROUTER_SESSION_ID:` line, then pass it explicitly on every CLI call:

```bash
composio search "send an email" --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
composio execute GMAIL_SEND_EMAIL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{"recipient_email":"a@b.com"}'
composio proxy https://gmail.googleapis.com/gmail/v1/users/me/profile --toolkit gmail --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

If a command reports no active connection, use the injected missing-tool URL template. Replace `{toolkit_slug}` with the needed toolkit slug and show that Phoenix URL to the user. Do not use `composio link`, managed Composio auth, or raw workspace/user IDs to create auth links.

## Workflow: search -> execute -> proxy

### Step 1 - Search for Tools

Use natural-language queries to find tool slugs in the provided session:

```bash
composio search "send an email" --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
composio search "create github issue" --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
composio search "list calendar events" --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

Search defaults to JSON output. The JSON includes matched tools, connected toolkit status, cached schema paths for primary tools, and a suggested next command.

Use multiple use-case queries in one request:

```bash
composio search "my emails" "my github issues" --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

Filter by toolkit and limit results:

```bash
composio search "create issue" --toolkits github --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
composio search "list calendar events" --toolkits google_calendar --limit 5 --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

Use human-readable output when inspecting results manually:

```bash
composio search "send an email" --human --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

Prefer `--limit` and `--toolkits` over shell truncation. Tool ranking and next-step guidance are more useful when the CLI receives and formats the full search response.

### Step 2 - Execute a Tool

Execute a tool slug inside the existing session:

```bash
composio execute GMAIL_SEND_EMAIL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{"recipient_email":"you@example.com","subject":"Hello","body":"Test"}'
composio execute GITHUB_CREATE_ISSUE --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{"owner":"acme","repo":"app","title":"Bug report"}'
```

`-d` and `--data` accept JSON, JSON with comments, or JS-style object literals:

```bash
composio execute GMAIL_SEND_EMAIL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{ recipient_email: "a@b.com", subject: "Hi", body: "Hello" }'
```

Read arguments from a file:

```bash
composio execute GITHUB_CREATE_ISSUE --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d @issue.json
```

Read arguments from stdin:

```bash
printf '{"recipient_email":"a@b.com"}' | composio execute GMAIL_SEND_EMAIL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d -
```

Fetch the CLI-facing schema before executing:

```bash
composio execute GMAIL_SEND_EMAIL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" --get-schema
```

Preview a call without executing it:

```bash
composio execute GITHUB_CREATE_ISSUE --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" --dry-run -d '{"owner":"acme","repo":"app","title":"Bug"}'
```

Execute independent calls concurrently:

```bash
composio execute --parallel --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" \
  GMAIL_SEND_EMAIL -d '{"recipient_email":"a@b.com"}' \
  GITHUB_CREATE_AN_ISSUE -d '{"owner":"acme","repo":"app","title":"Bug"}'
```

When a tool has exactly one `file_uploadable` input, inject a local file path with `--file`:

```bash
composio execute SOME_FILE_TOOL --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" --file ./report.pdf -d '{}'
```

If a tool has multiple uploadable fields, put the target field directly in `-d` instead of using `--file`.

### Step 3 - Proxy Provider APIs

Use `proxy` for curl-like access to toolkit APIs through Composio-managed auth in the provided session:

```bash
composio proxy https://gmail.googleapis.com/gmail/v1/users/me/profile --toolkit gmail --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
```

Send method, headers, and body:

```bash
composio proxy https://gmail.googleapis.com/gmail/v1/users/me/drafts --toolkit gmail --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" \
  -X POST -H 'content-type: application/json' -d '{"message":{"raw":"..."}}'
```

Supported methods are `GET`, `POST`, `PUT`, `DELETE`, and `PATCH`.

## Local Tools

`execute` can also run bundled local tools whose slugs start with `LOCAL_`. The package includes local toolkit declarations for:

1. `PEEKABOO` - macOS screen capture and GUI automation.
2. `CHROME_DEVTOOLS` - local Chrome automation through `chrome-devtools-mcp`.
3. `BEEPER_IMESSAGE` - local iMessage read and send workflows backed by `imessage-cli`.

Local tool slug format:

```text
LOCAL_<TOOLKIT>_<TOOL>
```

Examples:

```bash
composio execute LOCAL_PEEKABOO_VERSION --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" --get-schema
composio execute LOCAL_CHROME_DEVTOOLS_LIST_PAGES --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{}'
composio execute LOCAL_BEEPER_IMESSAGE_LIST_THREADS --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" -d '{}'
```

Local tools still use the same `execute` command and still require `COMPOSIO_API_KEY` and `--session-id` at the CLI layer. Supported platforms vary by toolkit. For example, Peekaboo and Beeper iMessage are macOS-focused, while Chrome DevTools supports common macOS, Linux, and Windows architectures.

Treat local tools as live local actions. Peekaboo can control the GUI, Chrome DevTools can inspect or modify browser pages, and Beeper iMessage can mutate Messages state.

## Command Reference

### `composio search`

```bash
composio search <query...> --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" [--toolkits text] [--limit integer] [--human]
```

Options:

```text
--session-id <session_id>  Existing Tool Router session id.
--toolkits <text>          Filter by toolkit slugs, comma-separated.
--limit <integer>          Maximum number of results, clamped to 1-1000.
--human                    Show formatted human-readable search output.
--json                     Force JSON output.
```

Behavior:

1. Calls the session search endpoint.
2. Searches one or more semantic use cases.
3. Filters output by toolkit when `--toolkits` is provided.
4. Writes JSON by default.
5. Fetches and caches primary tool schemas under `~/.composio/tool_definitions/` unless `COMPOSIO_CACHE_DIR` overrides the cache root.

### `composio execute`

```bash
composio execute <slug> --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" [-d, --data text] [--file path] [--dry-run] [--get-schema]
composio execute --parallel --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" <slug> -d <text> <slug> -d <text> ...
```

Options and flags:

```text
--session-id <session_id> Existing Tool Router session id.
-d, --data <text>         JSON or JS-style object arguments, @file, or - for stdin.
-p, --parallel            Execute repeated TOOL_SLUG -d <text> groups concurrently.
--file <path>             Inject a local file path into the single file_uploadable input.
--get-schema              Fetch and print the CLI-facing input schema without executing.
--dry-run                 Validate and preview the tool call without executing.
--account <text>          Connected account selector inside the provided session.
--skip-connection-check   Skip the connected-account check.
--skip-tool-params-check  Skip input validation against cached schema.
--skip-checks             Skip both checks above.
```

Behavior:

1. Calls the session execute endpoint for normal tool slugs.
2. Calls the session meta execute endpoint for supported `COMPOSIO_*` meta tools.
3. Executes `LOCAL_*` tools locally through the bundled local tools provider when available.
4. Validates inputs against cached schemas unless skipped.
5. Performs a session toolkit connection check unless skipped or executing a local tool.
6. Uploads file inputs when the tool schema marks fields as `file_uploadable`.
7. Stores very large successful outputs in an artifact file and prints a JSON summary with `storedInFile`.

### `composio proxy`

```bash
composio proxy <url> --toolkit <text> --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" [-X method] [-H header]... [-d data]
```

Options:

```text
--session-id <session_id> Existing Tool Router session id.
-t, --toolkit <text>      Toolkit slug whose connected account should be used.
-X, --method <method>     HTTP method: GET, POST, PUT, DELETE, PATCH.
-H, --header <header>     Header in "Name: value" format. Repeat for multiple.
-d, --data <data>         Request body as raw text, JSON, @file, or - for stdin.
--skip-connection-check   Skip the connected-account check.
```

Behavior:

1. Checks the toolkit connection in the provided session unless skipped.
2. Sends the request through the session proxy endpoint.
3. Parses JSON-ish request bodies when possible.
4. Prints string response data directly, JSON response data pretty-printed, or binary response metadata when present.

## Tips for Agents

1. Use `composio search` first unless the exact tool slug is already known.
2. Do not invent tool slugs. Use slugs returned by `search`, then use `--get-schema` to inspect inputs.
3. Keep `--session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"` explicit on every command.
4. Use `jq` for JSON output inspection.
5. Use `--get-schema` before complex `execute` payloads.
6. Use `--dry-run` before mutating calls when the payload is uncertain.
7. Use `--parallel` only for independent tool calls.
8. Skip checks only when you already know the session connection and schema state are valid.
9. For no-active-connection errors, use the injected missing-tool URL template.

## Slack Policy

Composio Slackbot tools are allowed for Slack API actions. Phoenix connects the workspace Slack account through the `slackbot` toolkit; the plain `slack` toolkit may be disabled in backend-created sessions. Use native Hermes Slack for ordinary current-thread replies and simple message delivery when it already satisfies the request. Use `composio-cli` with `--toolkits slackbot` for requested Slack API actions that native Hermes does not expose, including emoji reactions, search/history, user or channel metadata, pins, channel administration, and other Slack operations returned by `composio search`.

For Slack API work, search first and execute the returned tool slug with the injected session:

```bash
composio search "add an emoji reaction to a slack message" --toolkits slackbot --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID"
composio execute <RETURNED_SLACK_REACTION_TOOL_SLUG> --session-id "$COMPOSIO_TOOL_ROUTER_SESSION_ID" --dry-run -d '{"channel":"C123","timestamp":"1700000000.000100","name":"eyes"}'
```

If Slackbot auth is missing, use the injected missing-tool URL template with `slackbot` as the toolkit slug. Do not run `composio link`.

Composio trigger subscriptions for inbound Slack or Slackbot events remain rejected; inbound Slack events are handled by native Hermes Slack. This does not block direct Composio Slackbot tools in `search`, `execute`, or `proxy`.

Every supported command exposes `--help`; use it when needed.
