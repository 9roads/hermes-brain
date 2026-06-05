---
name: kernel-replays
description: Record, manage, and download video replays of Kernel browser sessions.
---

# Replays

Use replays to debug automation failures, document a browser run, or review what
happened visually.

## List

```bash
kernel browsers replays list <session_id> -o json
```

## Start

```bash
kernel browsers replays start <session_id> -o json
kernel browsers replays start <session_id> --framerate 30 --max-duration 300 -o json
```

## Stop

```bash
kernel browsers replays stop <session_id> <replay_id>
```

## Download

```bash
kernel browsers replays download <session_id> <replay_id> -o /tmp/replay.mp4
```

Avoid leaving long recordings running after the useful window has passed.
