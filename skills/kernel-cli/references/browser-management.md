---
name: kernel-browser-management
description: Create, list, view, automate, and delete Kernel browser sessions.
---

# Browser Management

Use browser management for one-off or long-running cloud Chrome sessions. In
Hermes, `kernel` is already installed and authenticated through `KERNEL_API_KEY`;
do not run interactive login commands.

Unless otherwise noted, `id` arguments refer to the browser session ID.

## Create Browsers

```bash
kernel browsers create -o json
kernel browsers create --stealth --headless -o json
kernel browsers create --start-url "https://example.com" -o json
kernel browsers create --profile-name my-profile -o json
```

Typical JSON output includes fields such as `session_id`, `cdp_ws_url`, and a
live browser view URL.

## Inspect Browsers

```bash
kernel browsers list -o json
kernel browsers get <session_id> -o json
kernel browsers view <session_id> -o json
```

`kernel browsers view` returns a live view URL for human monitoring or control.

## Delete Browsers

```bash
kernel browsers delete <session_id> -y
```

Always delete sessions when work is complete unless the user explicitly wants the
browser kept alive.

## Playwright Automation

```bash
kernel browsers playwright execute <session_id> '
  await page.goto("https://example.com");
  return await page.evaluate(() => document.title);
'
```

Use `return` when the caller needs a value back. Prefer Playwright for normal web
automation such as navigation, DOM inspection, form filling, clicking elements,
and extracting content.

## Screenshots

```bash
kernel browsers computer screenshot <session_id> --to /tmp/page.png
```

Use region flags when only part of the screen matters:

```bash
kernel browsers computer screenshot <session_id> --to /tmp/region.png --x 0 --y 0 --width 800 --height 600
```

## SSH And Port Forwarding

SSH into a browser VM for debugging or to expose local services. This requires
`websocat` to be installed locally.

```bash
kernel browsers ssh <session_id>
kernel browsers ssh <session_id> -R 3000:localhost:3000
kernel browsers ssh <session_id> -L 5432:localhost:5432
kernel browsers ssh <session_id> --setup-only
```

SSH alone does not count as browser activity. Keep the browser alive through its
session timeout or live view when needed.

## Common Pattern

```bash
SESSION=$(kernel browsers create -o json | jq -r '.session_id')

kernel browsers playwright execute "$SESSION" '
  await page.goto("https://example.com");
  return await page.content();
'

kernel browsers delete "$SESSION" -y
```
