# syntax=docker/dockerfile:1

ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest
FROM ${HERMES_BASE_IMAGE}

ARG SLACK_SDK_VERSION=3.42.0
ARG COMPOSIO_CLI_VERSION=0.1.3
ARG NORI_SLACK_CLI_VERSION=0.1.1
ARG LLM_WIKI_COMPILER_VERSION=0.7.0
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
    npm --version; \
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
    mkdir -p /opt/hermes/llmwiki; \
    cd /opt/hermes/llmwiki; \
    printf '{"private":true,"dependencies":{"llm-wiki-compiler":"%s"}}\n' "$LLM_WIKI_COMPILER_VERSION" > package.json; \
    pnpm install --prod --no-lockfile; \
    test -x /opt/hermes/llmwiki/node_modules/llm-wiki-compiler/dist/cli.js; \
    ln -sfn /opt/hermes/llmwiki/node_modules/llm-wiki-compiler/dist/cli.js /usr/local/bin/llmwiki; \
    llmwiki --version >/dev/null; \
    chown -R hermes:hermes /opt/hermes/llmwiki

COPY --chmod=0755 docker/entrypoint.sh /opt/hermes/image_base/entrypoint.sh
COPY --chmod=0755 docker/run-with-llmwiki.sh /opt/hermes/image_base/run-with-llmwiki.sh
COPY --chmod=0644 llmwiki/schema.json /opt/hermes/image_base/llmwiki/schema.json

RUN python3 -m json.tool /opt/hermes/image_base/llmwiki/schema.json >/dev/null

ENV PHOENIX_LLMWIKI_ROOT=/opt/data/workspace/company
ENV LLMWIKI_PROVIDER=openai
ENV LLMWIKI_MODEL=gpt-5.5
ENV LLMWIKI_EMBEDDING_MODEL=text-embedding-3-small

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes/image_base/entrypoint.sh"]
