# syntax=docker/dockerfile:1

ARG HERMES_BASE_IMAGE=nousresearch/hermes-agent:latest
FROM ${HERMES_BASE_IMAGE}

ARG OPENVIKING_VERSION=0.3.19
ARG HTTPX_VERSION=0.28.1

USER root

RUN uv pip install --python /opt/hermes/.venv/bin/python --no-cache-dir \
      "openviking==${OPENVIKING_VERSION}" \
      "httpx==${HTTPX_VERSION}" && \
    chown -R hermes:hermes /opt/hermes/.venv

COPY --chown=hermes:hermes plugins/memory/openviking_memory/ /opt/hermes/plugins/memory/openviking_memory/
COPY --chown=hermes:hermes openviking/memory-bundle/ /opt/hermes/openviking/memory-bundle/
COPY --chown=hermes:hermes openviking/memory-bundle/custom-memory/ /opt/hermes/openviking/company-memory/
COPY --chown=hermes:hermes openviking/ov.conf openviking/ovcli.conf /opt/hermes/openviking/
COPY --chmod=0755 docker/entrypoint.sh /opt/hermes/image_base/entrypoint.sh
COPY --chmod=0755 docker/run-with-openviking.sh /opt/hermes/image_base/run-with-openviking.sh

ENV OPENVIKING_CONFIG_FILE=/opt/data/openviking/ov.conf
ENV OPENVIKING_CLI_CONFIG_FILE=/opt/data/openviking/ovcli.conf
ENV OPENVIKING_ENDPOINT=http://127.0.0.1:1933
ENV OPENVIKING_ACCOUNT=default
ENV OPENVIKING_USER_SPACE=default
ENV OPENVIKING_AGENT_ID=hermes-memory

ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/opt/hermes/image_base/entrypoint.sh"]
