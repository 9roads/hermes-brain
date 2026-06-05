---
name: kernel-process-execution
description: Execute and manage processes inside Kernel browser VM environments.
---

# Process Execution

Use process execution for browser VM debugging, custom tooling, package
installation, sidecar processes, and data processing. The `<session_id>` argument
is the browser session ID.

## Execute Commands

```bash
kernel browsers process exec <session_id> -- ls -la /tmp
kernel browsers process exec <session_id> --cwd /tmp -- pwd
kernel browsers process exec <session_id> --timeout 30 -- long-running-command
kernel browsers process exec <session_id> --as-user chromium -- whoami
kernel browsers process exec <session_id> --as-root -- apt-get update
```

Use `--as-root` only when root privileges are actually required.

## Spawn Background Processes

```bash
kernel browsers process spawn <session_id> -- python3 -m http.server 8080
kernel browsers process spawn <session_id> --timeout 300 -- background-task
```

The spawn command returns a process ID. Keep that ID for status, output, stdin,
or kill commands.

## Inspect And Stream

```bash
kernel browsers process status <session_id> <process-id>
kernel browsers process stdout-stream <session_id> <process-id>
```

## Send Stdin

```bash
printf "input data" | base64 | xargs -I {} kernel browsers process stdin <session_id> <process-id> --data-b64 {}
```

## Kill Processes

```bash
kernel browsers process kill <session_id> <process-id>
kernel browsers process kill <session_id> <process-id> --signal TERM
kernel browsers process kill <session_id> <process-id> --signal KILL
```

Available signals include `TERM`, `KILL`, `INT`, and `HUP`.
