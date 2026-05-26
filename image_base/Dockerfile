# syntax=docker/dockerfile:1

ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest
FROM ${HERMES_BASE_IMAGE}

ARG SLACK_SDK_VERSION=3.42.0
ARG COMPOSIO_CLI_VERSION=0.1.3
ARG NORI_SLACK_CLI_VERSION=0.1.1
ARG LLM_WIKI_COMPILER_REPO=https://github.com/Ryner01/llm-wiki-compiler.git
ARG LLM_WIKI_COMPILER_REF=main
ARG HERMES_LCM_PLUGIN_REPO=https://github.com/stephenschoettler/hermes-lcm.git
ARG HERMES_LCM_PLUGIN_REF=c62de1978f8b1e7c8068f17b58b1737ff97e25b9
ARG NODE_VERSION=24.16.0
ARG PNPM_VERSION=10.18.3

USER root

RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir \
      "slack_sdk==${SLACK_SDK_VERSION}" && \
    chown -R hermes:hermes /opt/hermes/.venv

RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in \
      x86_64) node_arch="x64" ;; \
      aarch64|arm64) node_arch="arm64" ;; \
      *) echo "Unsupported Node.js architecture: $arch" >&2; exit 1 ;; \
    esac; \
    tmp_dir="$(mktemp -d)"; \
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" -o "$tmp_dir/node.tar.xz"; \
    tar -xJf "$tmp_dir/node.tar.xz" -C /usr/local --strip-components=1; \
    rm -rf "$tmp_dir"; \
    node --version; \
    corepack --version

RUN set -eux; \
    node -e 'const major = Number(process.versions.node.split(".")[0]); if (major < 24) { console.error(`Node >=24 is required, found ${process.versions.node}`); process.exit(1); }'; \
    if ! command -v pnpm >/dev/null 2>&1; then \
      command -v corepack >/dev/null; \
      corepack enable; \
      corepack prepare "pnpm@${PNPM_VERSION}" --activate; \
    fi; \
    command -v pnpm >/dev/null; \
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
    chown -R hermes:hermes /opt/hermes/nori-slack-cli; \
    tmp_llmwiki="$(mktemp -d)"; \
    git init "$tmp_llmwiki"; \
    cd "$tmp_llmwiki"; \
    git remote add origin "$LLM_WIKI_COMPILER_REPO"; \
    git fetch --depth 1 origin "$LLM_WIKI_COMPILER_REF"; \
    git checkout --detach FETCH_HEAD; \
    pnpm install --no-lockfile --ignore-scripts; \
    pnpm run build; \
    mkdir -p /opt/hermes/llmwiki; \
    node -e 'const fs = require("fs"); const pkg = JSON.parse(fs.readFileSync("package.json", "utf8")); fs.writeFileSync("/opt/hermes/llmwiki/package.json", JSON.stringify({ private: true, type: pkg.type, dependencies: pkg.dependencies }, null, 2) + "\n");'; \
    cp -R dist /opt/hermes/llmwiki/dist; \
    cd /opt/hermes/llmwiki; \
    pnpm install --prod --no-lockfile --ignore-scripts; \
    chmod 0755 /opt/hermes/llmwiki/dist/cli.js; \
    test -x /opt/hermes/llmwiki/dist/cli.js; \
    ln -sfn /opt/hermes/llmwiki/dist/cli.js /usr/local/bin/llmwiki-real; \
    printf '%s\n' \
      '#!/usr/bin/env bash' \
      'set -Eeuo pipefail' \
      'if [ -z "${DEEPSEEK_API_KEY:-}" ]; then' \
      '  echo "DEEPSEEK_API_KEY is required for llmwiki" >&2' \
      '  exit 1' \
      'fi' \
      'export OPENAI_API_KEY="$DEEPSEEK_API_KEY"' \
      'export OPENAI_BASE_URL="https://api.deepseek.com"' \
      'export LLMWIKI_PROVIDER="openai"' \
      'export LLMWIKI_MODEL="deepseek-v4-pro"' \
      'export LLMWIKI_EXTRACT_MODEL="deepseek-v4-flash"' \
      'exec /usr/local/bin/llmwiki-real "$@"' \
      > /usr/local/bin/llmwiki; \
    chmod 0755 /usr/local/bin/llmwiki; \
    DEEPSEEK_API_KEY=dummy llmwiki --help >/dev/null; \
    rm -rf "$tmp_llmwiki"; \
    chown -R hermes:hermes /opt/hermes/llmwiki; \
    mkdir -p /opt/hermes/image_base/llmwiki

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

COPY --chmod=0755 docker/entrypoint.sh /opt/hermes/image_base/entrypoint.sh
COPY --chmod=0755 docker/run-with-llmwiki.sh /opt/hermes/image_base/run-with-llmwiki.sh
COPY --chmod=0644 llmwiki/schema.json /opt/hermes/image_base/llmwiki/schema.json

RUN python3 -m json.tool /opt/hermes/image_base/llmwiki/schema.json >/dev/null

ENV PHOENIX_LLMWIKI_ROOT=/opt/data/workspace/company
ENV LLMWIKI_PROVIDER=openai
ENV LLMWIKI_MODEL=deepseek-v4-pro
ENV LLMWIKI_EXTRACT_MODEL=deepseek-v4-flash
ENV LLMWIKI_EXTRACT_CONCURRENCY=10
ENV LLMWIKI_EMBEDDING_MODEL=text-embedding-3-small

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes/image_base/entrypoint.sh"]
