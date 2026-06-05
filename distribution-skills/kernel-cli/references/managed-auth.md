---
name: kernel-managed-auth
description: Manage Kernel auth connections, login sessions, credential providers, and re-auth flows.
---

# Managed Auth

Managed Auth creates and maintains authenticated browser sessions. In Hermes,
avoid exposing credentials or `KERNEL_API_KEY` in output. Some managed-auth flows
are consequential because they affect stored login state; get confirmation before
creating, deleting, or submitting credentials for connections.

Commands live under `kernel auth connections`.

## Connections

```bash
kernel auth connections create --domain <domain> --profile-name <name> -o json
kernel auth connections create --domain github.com --profile-name gh --credential-name my-github-cred -o json
kernel auth connections list -o json
kernel auth connections list --domain github.com --profile-name gh -o json
kernel auth connections get <id> -o json
kernel auth connections delete <id> -y
```

Useful creation flags include `--credential-name`, `--credential-provider`,
`--credential-path`, `--credential-auto`, `--proxy-id`, `--proxy-name`,
`--login-url`, `--allowed-domain`, `--health-check-interval`, and
`--no-save-credentials`.

## Login Flows

```bash
kernel auth connections login <id> -o json
kernel auth connections login <id> --proxy-id <proxy_id> -o json
kernel auth connections follow <id> -o json
```

The login response can include hosted and live-view URLs for human completion.

Submit values only after explicit user confirmation:

```bash
kernel auth connections submit <id> --field username=myuser --field password=mypass
kernel auth connections submit <id> --sso-button-selector "//button[@id='google-sso']"
kernel auth connections submit <id> --mfa-option-id totp
```

## Credential Providers

```bash
kernel credential-providers list -o json
kernel credential-providers get <id> -o json
kernel credential-providers create --name <name> --provider-type onepassword --token <token>
kernel credential-providers test <id> -o json
kernel credential-providers list-items <id> -o json
kernel credential-providers delete <id> -y
```

Do not print provider tokens or credential values.

## Status Values

Connection statuses include `AUTHENTICATED` and `NEEDS_AUTH`.

Flow statuses include `IN_PROGRESS`, `SUCCESS`, `FAILED`, `EXPIRED`, and
`CANCELED`.

Flow steps include `DISCOVERING`, `AWAITING_INPUT`, `SUBMITTING`,
`AWAITING_EXTERNAL_ACTION`, and `COMPLETED`.
