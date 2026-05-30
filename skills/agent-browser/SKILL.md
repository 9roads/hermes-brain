---
name: agent-browser
description: Browser automation CLI for AI agents. Use for navigating websites, clicking, filling forms, screenshots, extraction, exploratory QA, and browser-based app testing.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [phoenix, browser, automation, kernel, cli]
    requires_toolsets: [terminal]
---

# Agent Browser

Use the preinstalled `agent-browser` CLI for browser automation. Phoenix bakes
the CLI into the Hermes image and sets `AGENT_BROWSER_PROVIDER=kernel` there.
Phoenix passes only the `KERNEL_API_KEY` secret at runtime. Do not print,
persist, echo, or include the key in command output, logs, reports, or final
responses.

Before using the browser, load the CLI-owned workflow content that matches the
installed version:

```bash
agent-browser skills get core
```

Use the returned instructions as the source of truth. For full command details
or templates when needed:

```bash
agent-browser skills get core --full
agent-browser skills list
```

Common commands:

```bash
agent-browser open https://example.com
agent-browser snapshot
agent-browser click @e2
agent-browser fill @e3 "value"
agent-browser screenshot /tmp/page.png
agent-browser close
```

Prefer accessibility-tree refs from `agent-browser snapshot` for interaction.
Use `agent-browser batch --bail ...` for multi-step flows when that reduces
process startup overhead.
