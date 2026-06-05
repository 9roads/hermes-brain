---
name: kernel-app-deployment
description: Deploy TypeScript/Python apps, invoke actions, and monitor logs in Kernel.
---

# App Deployment And Invocation

Use app deployment for reusable or serverless Kernel automations. For one-off
browser automation, use browser sessions directly.

Hermes is authenticated with `KERNEL_API_KEY`. Do not run interactive login
commands, and do not print or store secrets passed through deploy flags.

## Deploy

TypeScript deployments need a `package.json` next to the entrypoint:

```bash
kernel deploy index.ts -o json
```

Python deployments need a `pyproject.toml` next to the entrypoint:

```bash
kernel deploy main.py -o json
```

With environment variables:

```bash
kernel deploy index.ts --env API_KEY=secret --env DB_URL=postgres://example -o json
kernel deploy index.ts --env-file .env -o json
```

Do not echo secret env values into logs or final responses.

## Invoke

```bash
kernel invoke my-app scrape -o json
kernel invoke my-app scrape --payload '{"url": "https://example.com"}' -o json
kernel invoke my-app scrape --payload-file payload.json -o json
kernel invoke my-app scrape --payload '{"url": "https://example.com"}' --sync -o json
```

Synchronous invocations time out after 60 seconds. JSON payloads are limited to
4.5 MB.

## Logs

```bash
kernel logs my-app
kernel logs my-app --follow
kernel logs my-app --since 1h --with-timestamps
```

Log lines longer than 64 KiB may be truncated. For large results, write artifacts
to storage and log references.

## Troubleshooting

- `401 Unauthorized`: check that `KERNEL_API_KEY` exists in the runtime env; do
  not run interactive `kernel login` in Hermes.
- Missing entrypoint: confirm the deployment file exists at the path used.
- Syntax or dependency errors: run local lint/typecheck/tests before deploying
  when the app source is in the workspace.
