# Codex App Creator Project Instructions

These instructions apply to this project directory.

## Scope

- This project may contain coding work delegated by Hermes, but the output must be a frontend-only static app.
- Build only frontend applications: static HTML/CSS/JS, Vite, React, and browser-side libraries are allowed.
- Do not build or add servers, API routes, SSR, server actions, cron jobs, hosted workers, external databases, or secret-bearing backend SDKs.
- Persist app state only in the browser: `localStorage`, `sessionStorage`, IndexedDB, Cache API, OPFS, URL state, or downloadable/importable files.
- Do not put secrets in client code. If a feature requires a secret, report the blocker and propose a browser-only alternative.

## Project Root

- Treat this directory as the project root.
- Keep source, generated assets, screenshots, temporary scaffolds, build output, and publish scratch files under this directory.
- Do not create sibling project directories or store coding data outside this directory.

## Package Manager

- Use npm for all project package work.
- Use `npm`, `npm create`, `npm install`, `npm run`, and `npx`.
- Do not use pnpm, Yarn, or Bun in this project.
- Keep npm cache under this project root with `cache=.npm-cache` in `.npmrc`.

## New App Bootstrap

If this directory has no `package.json`, create the Vite app in this directory.
Because this directory already contains `AGENTS.md`, scaffold Vite into a temporary
subdirectory first, then move the scaffolded files into the project root:

```bash
printf 'cache=.npm-cache\n' > .npmrc
npm create vite@latest .vite-bootstrap -- --template react-ts
(shopt -s dotglob nullglob; mv .vite-bootstrap/* .)
rmdir .vite-bootstrap
npm install
```

Do not leave the app nested under `.vite-bootstrap` or another child directory.
If a `.gitignore` exists, include `.npm-cache/`.

## shadcn/ui

- Install and use shadcn/ui by default for every Vite or React project.
- Add only the shadcn components the app actually uses.
- Use semantic tokens and accessible component composition.

Initialize shadcn/ui after the Vite app exists:

```bash
npx --yes shadcn@latest init --yes
npx --yes skills add shadcn/ui
npx --yes shadcn@latest info --json
```

If `shadcn init` reports missing Vite, Tailwind, or alias setup, fix the project
with npm commands and rerun `npx --yes shadcn@latest init --yes`.

Fetch component docs when needed:

```bash
npx --yes shadcn@latest docs button
```

Add components explicitly, for example:

```bash
npx --yes shadcn@latest add button card input label tabs table dialog sheet tooltip
```

## Build And Validate

Every app must build to static hostable output, normally `dist/`.

```bash
npm run build
```

Run additional project scripts when present and relevant:

```bash
npm run lint --if-present
npm run test --if-present
```

For visual apps, inspect a local preview when practical. Fix blank screens,
console errors, broken responsive layouts, missing assets, and state persistence
issues before deployment.

## Simple Anonymous Deploy To here.now

After a successful build, publish `dist/` to here.now from the project root.
Use SPA mode when the app has client-side routes. Keep this flow simple:
anonymous static deploy only. Do not use here.now account auth, Drive, custom
domain, payment, password, update, or API-key flows unless the user explicitly
asks for one of those features later.

```bash
PROFILE_NAME="${PHOENIX_HERMES_PROFILE_NAME:-phoenix}"
PROFILE_DIR="${HERMES_HOME:-/opt/data/profiles/$PROFILE_NAME}"
PUBLISH="$PROFILE_DIR/skills/codex-app-creator/scripts/publish.sh"
test -x "$PUBLISH"

bash "$PUBLISH" dist --client hermes --spa
```

Report the final `siteUrl` from the publish output. Anonymous sites expire in 24
hours; include the claim URL only if the publish output returns one.
