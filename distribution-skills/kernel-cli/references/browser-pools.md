---
name: kernel-browser-pools
description: Manage pre-warmed browser pools for fast browser acquisition and release.
---

# Browser Pools

Browser pools keep pre-warmed browsers ready for repeated short tasks. Use pools
for high-throughput automation or when browser startup latency matters. For
simple one-off work, create browsers directly.

## Create

```bash
kernel browser-pools create --name my-pool --size 5 -o json
kernel browser-pools create --name my-pool --size 10 --fill-rate 5 --stealth --headless -o json
kernel browser-pools create --name auth-pool --size 5 --profile-name my-profile --save-changes -o json
```

Useful flags include `--timeout`, `--start-url`, `--profile-id`,
`--profile-name`, `--save-changes`, `--proxy-id`, `--extension`, `--viewport`,
`--headless`, `--stealth`, and `--kiosk`.

## Inspect And Update

```bash
kernel browser-pools list -o json
kernel browser-pools get my-pool -o json
kernel browser-pools update my-pool --size 10 -o json
kernel browser-pools flush my-pool
```

## Acquire And Release

```bash
kernel browser-pools acquire my-pool -o json
kernel browser-pools acquire my-pool --timeout 30 -o json
kernel browser-pools release my-pool --session-id <session_id>
kernel browser-pools release my-pool --session-id <session_id> --reuse
```

## Delete

```bash
kernel browser-pools delete my-pool --force
```

Deleting or flushing a pool can interrupt active work. Confirm before doing it
for user-owned pools.
