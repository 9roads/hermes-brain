---
name: codex-app-creator
description: Use for any task that requires programming, coding, implementation, code edits, debugging, app creation, website creation, UI work, feature work, validation, redeployment, or publishing a simple static site. Delegates coding work to Codex CLI.
---

# Codex App Creator

Use this skill whenever the user asks Hermes to do programming work. Hermes is
the orchestrator, not the coding agent: it creates or locates the project
directory, initializes Bun React/shadcn app projects when needed, and delegates
implementation, validation, and deployment to Codex CLI.

Hermes does not edit app code or deploy manually for new projects. New static
frontend app projects are bootstrapped with Bun before Codex starts.

## Bootstrap A New Project

Derive a short lowercase slug from the user's app name. New project roots must be
under `/opt/data/workspace/<project>`.

```bash
WORKSPACE=/opt/data/workspace
PROJECT=my-dashboard
PROJECT_DIR="$WORKSPACE/$PROJECT"

mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

if [ ! -f package.json ]; then
  bun init --react=shadcn --yes
  bunx --bun skills add shadcn/ui --yes
  test -f .agents/skills/shadcn/SKILL.md
fi
```

For a new project, do not create a custom Phoenix `AGENTS.md` or other
Phoenix-specific instruction files before invoking Codex. Bun's React/shadcn
template plus the shadcn skill install are the project baseline. Leave those
generated files in place.

## Existing Projects

Work on an existing project when the user explicitly points to it. If the
project lacks `package.json` and the request is for a static frontend app,
bootstrap it with the same Bun commands from the new-project flow. If the
project already has `package.json`, do not reinitialize it; tell Codex to use Bun
for package work unless existing project instructions make that impossible.

If an existing project is outside `/opt/data/workspace`, keep the user's source
path intact. Put clones, scratch copies, exports, screenshots, and new generated
project data under `/opt/data/workspace/<project>`.

## Codex Invocation

Use `codex exec` with GPT-5.5 and high reasoning effort. If that model is
unavailable, report the blocker instead of silently switching models. Use a PTY
when invoking through Hermes terminal tooling.

```bash
codex exec \
  --model gpt-5.5 \
  -c model_reasoning_effort=high \
  -c sandbox_workspace_write.network_access=true \
  --sandbox workspace-write \
  --skip-git-repo-check \
  --cd "$PROJECT_DIR" \
  "$PROMPT"
```

For long tasks, start Codex in the background with a PTY and poll logs. Avoid
`--yolo`; only use full sandbox bypass inside an external isolated runner.

Use this prompt shape:

```text
Implement the user's coding request in this directory.

This is a Bun-managed, frontend-only static app project. Use Bun commands only:
`bun`, `bun run`, `bun install`, `bun add`, `bun remove`, and `bunx --bun`. Do
not use npm, npx, pnpm, or Yarn. Use the existing Bun React/shadcn project
baseline; for shadcn/ui work, use `bunx --bun shadcn@latest ...` and add only
the components the app actually uses.

Keep the app browser-only: no servers, API routes, SSR, server actions, cron
jobs, external databases, workers, or secret-bearing backend SDKs. Persist app
state only in browser storage, URL state, or importable/exportable files. If the
user's request cannot be satisfied as a static frontend app, report the blocker
and offer the closest browser-only alternative. Keep all generated project data
inside this directory.

After implementation, run `bun run build`, then run relevant `bun run lint` or
`bun run test` scripts when they exist. Deploy the static build to here.now
anonymously. Report changed files, validation results, the final siteUrl, and
the anonymous expiry/claim URL if the publish output provides one.
```

## Simple Anonymous Static Deploy

Static publishing is part of this skill. Do not load a separate publishing skill
or use here.now account, Drive, custom domain, auth, payment, password, or update
flows for normal app-creator work.

Use only the bundled publish helper after `bun run build` succeeds:

```bash
PROFILE_NAME="${PHOENIX_HERMES_PROFILE_NAME:-phoenix}"
PROFILE_DIR="${HERMES_HOME:-/opt/data/profiles/$PROFILE_NAME}"
PUBLISH="$PROFILE_DIR/skills/codex-app-creator/scripts/publish.sh"
test -x "$PUBLISH"

bash "$PUBLISH" dist --client hermes --spa
```

This creates a fresh anonymous site. Anonymous sites expire in 24 hours unless
the publish output includes a claim URL and the user claims it.

## Handoff

Relay Codex's changed files, validation status, and here.now URL. If Codex could
not deploy, report the blocker and the last successful validation command.
