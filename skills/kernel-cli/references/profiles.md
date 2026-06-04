---
name: kernel-profiles
description: Create and manage persistent browser profiles for cookies, local storage, and session state.
---

# Profiles

Profiles store persistent browser state such as cookies, local storage, and site
preferences. Use them when an automation needs reusable logged-in state or
consistent browser settings.

## Create

```bash
kernel profiles create --name my-profile -o json
kernel profiles create -o json
```

## Inspect

```bash
kernel profiles list -o json
kernel profiles get my-profile -o json
```

## Use With Browsers

```bash
kernel browsers create --profile-name my-profile -o json
```

## Download

```bash
kernel profiles download my-profile --to /tmp/profile.zip
```

## Delete

```bash
kernel profiles delete my-profile -y
```

Do not delete profiles unless the user explicitly asks, because profiles can
contain durable browser state for future work.
