# syntax=docker/dockerfile:1

ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:sha-bec2250d2c8349fc85201bcd1aa39bcaa766a555
ARG NODE_VERSION=24.16.0
ARG BUN_VERSION=1.3.14
ARG PNPM_VERSION=11.3.0

FROM node:${NODE_VERSION}-bookworm-slim AS node_runtime
FROM oven/bun:${BUN_VERSION}-debian AS bun_runtime
FROM ${HERMES_BASE_IMAGE}

ARG BUN_VERSION
ARG PNPM_VERSION
ARG OPENVIKING_VERSION=0.3.19
ARG HTTPX_VERSION=0.28.1
ARG SLACK_SDK_VERSION=3.42.0
ARG TIKTOKEN_VERSION=0.13.0
ARG COMPOSIO_CLI_VERSION=0.1.3
ARG NORI_SLACK_CLI_VERSION=0.1.1
ARG CODEX_CLI_VERSION=0.134.0
ARG HERMES_LCM_PLUGIN_REPO=https://github.com/stephenschoettler/hermes-lcm.git
ARG HERMES_LCM_PLUGIN_REF=c62de1978f8b1e7c8068f17b58b1737ff97e25b9

USER root

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /usr/local/lib/node_modules/corepack /usr/local/lib/node_modules/corepack
COPY --from=node_runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=bun_runtime /usr/local/bin/bun /usr/local/bin/bun

RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir \
      "openviking==${OPENVIKING_VERSION}" \
      "httpx==${HTTPX_VERSION}" \
      "slack_sdk==${SLACK_SDK_VERSION}" \
      "tiktoken==${TIKTOKEN_VERSION}" && \
    test -x /opt/hermes/.venv/bin/python && \
    test -x /opt/hermes/.venv/bin/hermes && \
    test -x /opt/hermes/.venv/bin/openviking && \
    test -x /opt/hermes/.venv/bin/ov && \
    printf '%s\n' '#!/bin/sh' 'exec /opt/hermes/.venv/bin/python "$@"' > /usr/local/bin/python && \
    chmod 0755 /usr/local/bin/python && \
    printf '%s\n' '#!/bin/sh' 'exec /opt/hermes/.venv/bin/hermes "$@"' > /usr/local/bin/hermes && \
    chmod 0755 /usr/local/bin/hermes && \
    printf '%s\n' '#!/bin/sh' 'exec /opt/hermes/.venv/bin/hermes "$@"' > /opt/hermes/hermes && \
    chmod 0755 /opt/hermes/hermes && \
    ln -sfn /opt/hermes/.venv/bin/openviking /usr/local/bin/openviking && \
    ln -sfn /opt/hermes/.venv/bin/ov /usr/local/bin/ov && \
    export PATH="/opt/hermes/.venv/bin:$PATH" && \
    hash -r && \
    python -c 'import tiktoken' && \
    /usr/local/bin/python -c 'import tiktoken' && \
    python --version && \
    hermes --help >/dev/null && \
    /usr/local/bin/hermes --help >/dev/null && \
    /opt/hermes/hermes --help >/dev/null && \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" hermes --help >/dev/null && \
    openviking --version && \
    ov --version && \
    chown -R hermes:hermes /opt/hermes/.venv

COPY python/phoenix_slack_socket_router.py /tmp/phoenix_slack_socket_router.py

RUN /opt/hermes/.venv/bin/python - <<'PY'
from pathlib import Path
import py_compile
import shutil
import sysconfig

purelib = Path(sysconfig.get_path("purelib"))
module = purelib / "phoenix_slack_socket_router.py"
pth = purelib / "phoenix_slack_socket_router.pth"

shutil.copyfile("/tmp/phoenix_slack_socket_router.py", module)
py_compile.compile(str(module), doraise=True)
pth.write_text("import phoenix_slack_socket_router\n", encoding="utf-8")
shutil.chown(module, user="hermes", group="hermes")
shutil.chown(pth, user="hermes", group="hermes")
print(f"Installed Phoenix Slack Socket Mode router patch: {module}")
PY

RUN /opt/hermes/.venv/bin/python - <<'PY'
from pathlib import Path
import py_compile

import openai

sdk_file = Path(openai.__file__).resolve().parent / "lib" / "_parsing" / "_responses.py"
old = "for output in response.output:"
new = "for output in (response.output or []):"
source = sdk_file.read_text(encoding="utf-8")

if new in source:
    print(f"OpenAI Responses parser already patched: {sdk_file}")
elif old in source:
    sdk_file.write_text(source.replace(old, new, 1), encoding="utf-8")
    py_compile.compile(str(sdk_file), doraise=True)
    print(f"Patched OpenAI Responses parser for null terminal output: {sdk_file}")
else:
    raise SystemExit(f"OpenAI Responses parser patch target not found: {sdk_file}")
PY

RUN set -eux; \
    ln -sfn ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm; \
    ln -sfn ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx; \
    ln -sfn ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack; \
    ln -sfn /usr/local/bin/bun /usr/local/bin/bunx; \
    node --version; \
    npm --version; \
    npx --version; \
    bun --version; \
    bun --revision; \
    bunx --version >/dev/null; \
    corepack --version; \
    corepack enable; \
    corepack prepare "pnpm@${PNPM_VERSION}" --activate; \
    pnpm --version

RUN set -eux; \
    node -e 'const major = Number(process.versions.node.split(".")[0]); if (major < 24) { console.error(`Node >=24 is required, found ${process.versions.node}`); process.exit(1); }'; \
    command -v pnpm >/dev/null; \
    pnpm --version; \
    mkdir -p /opt/hermes/codex-cli; \
    cd /opt/hermes/codex-cli; \
    printf '{"private":true,"dependencies":{"@openai/codex":"%s"}}\n' "$CODEX_CLI_VERSION" > package.json; \
    pnpm install --prod --no-lockfile; \
    test -x /opt/hermes/codex-cli/node_modules/.bin/codex; \
    /opt/hermes/codex-cli/node_modules/.bin/codex --version; \
    chown -R hermes:hermes /opt/hermes/codex-cli; \
    mkdir -p /opt/hermes/composio-cli; \
    cd /opt/hermes/composio-cli; \
    printf '{"private":true,"dependencies":{"loisa-composio-cli":"%s"}}\n' "$COMPOSIO_CLI_VERSION" > package.json; \
    pnpm install --prod --no-lockfile; \
    test -x /opt/hermes/composio-cli/node_modules/loisa-composio-cli/dist/cli.js; \
    ln -sfn /opt/hermes/composio-cli/node_modules/loisa-composio-cli/dist/cli.js /usr/local/bin/composio; \
    chown -R hermes:hermes /opt/hermes/composio-cli; \
    mkdir -p /opt/hermes/nori-slack-cli; \
    cd /opt/hermes/nori-slack-cli; \
    printf '{"private":true,"dependencies":{"nori-slack-cli":"%s"}}\n' "$NORI_SLACK_CLI_VERSION" > package.json; \
    pnpm install --prod --no-lockfile; \
    test -x /opt/hermes/nori-slack-cli/node_modules/nori-slack-cli/dist/index.js; \
    ln -sfn /opt/hermes/nori-slack-cli/node_modules/nori-slack-cli/dist/index.js /usr/local/bin/nori-slack; \
    nori-slack --help >/dev/null; \
    chown -R hermes:hermes /opt/hermes/nori-slack-cli

RUN set -eux; \
    plugin_dir="/opt/hermes/plugins/hermes-lcm"; \
    tmp_lcm="$(mktemp -d)"; \
    git init "$tmp_lcm"; \
    cd "$tmp_lcm"; \
    git remote add origin "$HERMES_LCM_PLUGIN_REPO"; \
    git fetch --depth 1 origin "$HERMES_LCM_PLUGIN_REF"; \
    git checkout --detach FETCH_HEAD; \
    mkdir -p /opt/hermes/plugins; \
    rm -rf "$plugin_dir"; \
    mkdir -p "$plugin_dir"; \
    tar --exclude=.git --exclude=.github -cf - . | tar -xf - -C "$plugin_dir"; \
    test -f "$plugin_dir/plugin.yaml"; \
    test -f "$plugin_dir/__init__.py"; \
    rm -rf "$tmp_lcm"; \
    chown -R hermes:hermes "$plugin_dir"

COPY --chmod=0755 docker/codex /usr/local/bin/codex
COPY --chmod=0755 docker/entrypoint.sh /opt/hermes/image_base/entrypoint.sh
COPY --chown=hermes:hermes plugins/memory/openviking_memory/ /opt/hermes/plugins/memory/openviking_memory/
COPY --chown=hermes:hermes openviking/custom-memory/ /opt/hermes/openviking/custom-memory/
COPY --chown=hermes:hermes openviking/ov.conf openviking/ovcli.conf /opt/hermes/openviking/
COPY --chmod=0755 docker/run-with-openviking.sh /opt/hermes/image_base/run-with-openviking.sh

ENV BUN_INSTALL_GLOBAL_STORE=1
ENV OPENVIKING_ENDPOINT=http://127.0.0.1:1933
ENV OPENVIKING_ACCOUNT=default
ENV OPENVIKING_USER_SPACE=default
ENV OPENVIKING_AGENT_ID=hermes-memory

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes/image_base/entrypoint.sh"]
