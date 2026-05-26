# Phoenix Hermes llmwiki Image

This directory is image build source, not Hermes profile-distribution payload.
`hermes/distribution.yaml` intentionally does not include `image_base/`.

Build the custom image from the repository root:

```bash
docker build -t phoenix-hermes-llmwiki:local hermes/image_base
```

Run it with a persistent `/opt/data` volume and OpenAI credentials:

```bash
docker run --rm -it \
  -v phoenix-hermes-data:/opt/data \
  -e OPENAI_BASE_URL="$OPENAI_BASE_URL" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  phoenix-hermes-llmwiki:local gateway run -v
```

The image installs `llm-wiki-compiler` `0.7.0`, `slack_sdk` `3.42.0`,
`loisa-composio-cli` `0.1.3`, and `nori-slack-cli` `0.1.1`. On gateway startup,
the wrapper installs or updates the Phoenix Hermes profile, verifies the
profile-owned `nori-slack-cli` and `llmwiki-cli` skills exist, ensures the shared
`phoenix-ingestion` Kanban board exists, creates the llmwiki project at
`/opt/data/workspace/company`, starts `llmwiki watch` from that directory, and
then runs the requested Hermes command.

Runtime llmwiki layout:

- `/opt/data/workspace/company/sources/`: raw exported Slack sources
- `/opt/data/workspace/company/wiki/`: compiled company wiki
- `/opt/data/workspace/company/.llmwiki/`: compiler state, locks, and embeddings
- `/opt/data/workspace/company/.llmwiki/schema.json`: Phoenix company wiki schema

The image seeds `.llmwiki/schema.json` from
`/opt/hermes/image_base/llmwiki/schema.json` when the project does not already
have a schema. Set `PHOENIX_LLMWIKI_SCHEMA_FORCE=1` to reinstall the image
schema over an existing runtime schema.

Default llmwiki env:

- `LLMWIKI_PROVIDER=openai`
- `LLMWIKI_MODEL=gpt-5.5`
- `LLMWIKI_EMBEDDING_MODEL=text-embedding-3-small`
- `PHOENIX_LLMWIKI_ROOT=/opt/data/workspace/company`

The default watch log is `/opt/data/logs/llmwiki-watch.log`.
