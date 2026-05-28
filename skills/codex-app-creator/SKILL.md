---
name: codex-app-creator
description: Use for any task that requires programming, coding, implementation, code edits, debugging, app creation, website creation, UI work, feature work, validation, or redeployment. Delegates coding work to Codex CLI.
---

# Codex App Creator

Use this skill whenever the user asks Hermes to do programming work. Hermes is
the orchestrator, not the coding agent: it creates or locates the project
directory, ensures the project has app-creator instructions in `AGENTS.md`, and
delegates implementation, validation, and deployment to Codex CLI.

Hermes does not scaffold Vite, install packages, initialize shadcn/ui, edit app
code, or deploy manually for new projects. Codex reads the copied `AGENTS.md` and
does that work inside the project.

## Bootstrap A New Project

Derive a short lowercase slug from the user's app name. New project roots must be
under `/opt/data/workspace/<project>`.

```bash
WORKSPACE=/opt/data/workspace
PROJECT=my-dashboard
PROJECT_DIR="$WORKSPACE/$PROJECT"
AGENTS_TEMPLATE="${PHOENIX_CODEX_APP_CREATOR_AGENTS:-/opt/hermes/image_base/codex-app-creator/AGENTS.md}"

mkdir -p "$PROJECT_DIR"
cp "$AGENTS_TEMPLATE" "$PROJECT_DIR/AGENTS.md"
```

For a new project, do not create any other files before invoking Codex. The
project `AGENTS.md` is the source of truth for Vite, npm, shadcn/ui,
browser-local state, static build output, and here.now deployment rules.

## Existing Projects

Work on an existing project when the user explicitly points to it. If the
project lacks `AGENTS.md`, copy the same template there before invoking Codex. If
it already has `AGENTS.md`, do not overwrite it; include the template path in the
Codex prompt and tell Codex to reconcile the existing project instructions with
the app-creator requirements.

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
Read ./AGENTS.md first, then implement the user's coding request in this
directory.

Use the project AGENTS.md rules for package manager, Vite bootstrapping,
shadcn/ui setup, browser-only persistence, static build validation, and here.now
deployment. If the user's request cannot be satisfied as a static frontend app,
report the blocker and offer the closest browser-only alternative. Keep all
generated project data inside this directory.

After implementation, run the required validation and deploy to here.now. Report
changed files, validation results, and the final siteUrl.
```

## Handoff

Relay Codex's changed files, validation status, and here.now URL. If Codex could
not deploy, report the blocker and the last successful validation command.
