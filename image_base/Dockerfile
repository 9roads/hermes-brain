# syntax=docker/dockerfile:1

ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest
FROM ${HERMES_BASE_IMAGE}

ARG OPENVIKING_VERSION=0.3.19
ARG HTTPX_VERSION=0.28.1
ARG SLACK_SDK_VERSION=3.42.0
ARG COMPOSIO_CLI_VERSION=0.1.3
ARG NORI_SLACK_CLI_VERSION=0.1.1
ARG PNPM_VERSION=10.18.3

USER root

RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir \
      "openviking==${OPENVIKING_VERSION}" \
      "httpx==${HTTPX_VERSION}" \
      "slack_sdk==${SLACK_SDK_VERSION}" && \
    chown -R hermes:hermes /opt/hermes/.venv

RUN set -eux; \
    if ! command -v pnpm >/dev/null 2>&1; then \
      command -v corepack >/dev/null; \
      corepack enable; \
      corepack prepare "pnpm@${PNPM_VERSION}" --activate; \
    fi; \
    command -v pnpm >/dev/null; \
    mkdir -p /opt/hermes/composio-cli; \
    cd /opt/hermes/composio-cli; \
    printf '{"private":true,"dependencies":{"loisa-composio-cli":"%s"}}\n' "$COMPOSIO_CLI_VERSION" > package.json; \
    pnpm install --prod --lockfile=false; \
    test -x /opt/hermes/composio-cli/node_modules/loisa-composio-cli/dist/cli.js; \
    ln -sfn /opt/hermes/composio-cli/node_modules/loisa-composio-cli/dist/cli.js /usr/local/bin/composio; \
    chown -R hermes:hermes /opt/hermes/composio-cli; \
    mkdir -p /opt/hermes/nori-slack-cli; \
    cd /opt/hermes/nori-slack-cli; \
    printf '{"private":true,"dependencies":{"nori-slack-cli":"%s"}}\n' "$NORI_SLACK_CLI_VERSION" > package.json; \
    pnpm install --prod --lockfile=false; \
    test -x /opt/hermes/nori-slack-cli/node_modules/nori-slack-cli/dist/index.js; \
    ln -sfn /opt/hermes/nori-slack-cli/node_modules/nori-slack-cli/dist/index.js /usr/local/bin/nori-slack; \
    nori-slack --help >/dev/null; \
    chown -R hermes:hermes /opt/hermes/nori-slack-cli

COPY --chown=hermes:hermes plugins/memory/openviking_memory/ /opt/hermes/plugins/memory/openviking_memory/
COPY --chown=hermes:hermes openviking/memory-bundle/ /opt/hermes/openviking/memory-bundle/
COPY --chown=hermes:hermes openviking/memory-bundle/custom-memory/ /opt/hermes/openviking/company-memory/
COPY --chown=hermes:hermes openviking/ov.conf openviking/ovcli.conf /opt/hermes/openviking/
COPY --chmod=0755 docker/entrypoint.sh /opt/hermes/image_base/entrypoint.sh
COPY --chmod=0755 docker/run-with-openviking.sh /opt/hermes/image_base/run-with-openviking.sh

ENV OPENVIKING_ENDPOINT=http://127.0.0.1:1933
ENV OPENVIKING_ACCOUNT=default
ENV OPENVIKING_USER_SPACE=default
ENV OPENVIKING_AGENT_ID=hermes-memory

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes/image_base/entrypoint.sh"]
