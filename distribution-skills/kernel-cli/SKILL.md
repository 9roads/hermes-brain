---
name: kernel-cli
description: Use the preinstalled Kernel CLI for cloud browser automation, browser VM control, app deployment, profiles, proxies, extensions, managed auth, and replays.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [phoenix, kernel, browser, automation, cli]
    requires_toolsets: [terminal]
---

# Kernel CLI

Use the preinstalled `kernel` CLI for browser automation and Kernel resource
management. Phoenix bakes `@onkernel/cli` into the Hermes image and passes the
existing `KERNEL_API_KEY` secret at runtime.

Do not print, paste, persist, echo, or include `KERNEL_API_KEY` in command
output, logs, reports, or final responses. Do not run interactive `kernel login`
inside Hermes; this runtime is configured for API-key auth.

Prefer JSON output with `-o json` or `--output json` when scripting, and parse it
with tools such as `jq` instead of scraping human-readable output.

## Quick Start

```bash
kernel --version
kernel browsers create -o json
```

Create a browser, run Playwright code, take a screenshot, and clean up:

```bash
SESSION=$(kernel browsers create -o json | jq -r '.session_id')

kernel browsers playwright execute "$SESSION" '
  await page.goto("https://example.com");
  return await page.evaluate(() => document.title);
'

kernel browsers computer screenshot "$SESSION" --to /tmp/kernel-page.png
kernel browsers delete "$SESSION" -y
```

Use `return` in Playwright snippets when the caller needs a value back. Use
computer controls for OS-level mouse, keyboard, and screenshot work only when
Playwright is not enough.

## References

- [Browser Management](./references/browser-management.md) - create, list, view, automate, and delete browser sessions.
- [Computer Controls](./references/computer-controls.md) - OS-level mouse, keyboard, scroll, drag, and screenshots.
- [Process Execution](./references/process-execution.md) - execute and manage processes inside browser VMs.
- [Filesystem Operations](./references/filesystem-ops.md) - read, write, upload, and download files in browser VMs.
- [Profiles](./references/profiles.md) - persistent browser state and cookies.
- [Managed Auth](./references/managed-auth.md) - managed login connections and flows.
- [Browser Pools](./references/browser-pools.md) - pre-warmed browser pools for repeated tasks.
- [Proxies](./references/proxies.md) - datacenter, ISP, residential, mobile, and custom proxies.
- [Extensions](./references/extensions.md) - upload, download, and manage Chrome extensions.
- [Replays](./references/replays.md) - record and download browser session videos.
- [App Deployment](./references/app-deployment.md) - deploy and invoke Kernel apps.
