---
name: linkdapi-python-sdk
description: Use the preinstalled LinkdAPI Python SDK in Hermes for professional profile, company, job, and market-intelligence data enrichment with LINKD_API_KEY runtime auth.
version: 0.1.0
platforms: [linux]
metadata:
  hermes:
    tags: [loisa, linkdapi, python, sdk, enrichment]
    requires_toolsets: [terminal]
required_environment_variables:
  - name: LINKD_API_KEY
    prompt: LinkdAPI API key
    help: Get a key at https://linkdapi.com/?p=signup
    required_for: LinkdAPI professional profile, company, and job data enrichment
---

# LinkdAPI Python SDK

Use the preinstalled `linkdapi` Python package when a task needs structured
professional-network data: profile enrichment, company intelligence, job-market
analysis, recruiting research, contact discovery, CRM enrichment, due
diligence, or batch data analysis.

Hermes receives the LinkdAPI credential as `LINKD_API_KEY`. Do not print, paste,
persist, echo, or include `LINKD_API_KEY` in command output, logs, reports, or
final responses.

Prefer the SDK over browser scraping or ad hoc HTTP calls for supported profile,
company, job, post, search, and lookup endpoints. Use normal web research tools
instead when the user needs general public web search, source reading, or facts
outside the LinkdAPI data surface.

## Quick Start

```bash
python - <<'PY'
import json
import os
from linkdapi import LinkdAPI

api_key = os.environ.get("LINKD_API_KEY")
if not api_key:
    raise SystemExit("LINKD_API_KEY is not set in this Hermes terminal")

client = LinkdAPI(api_key)
result = client.get_full_profile(username="ryanroslansky")
print(json.dumps(result, indent=2))
PY
```

For one or a few requests, use the synchronous `LinkdAPI` client. For batches or
multiple independent endpoint calls, use `AsyncLinkdAPI` with `asyncio.gather`
and keep concurrency bounded.

## Usage Notes

- Initialize clients from `os.environ["LINKD_API_KEY"]`; never hardcode API keys.
- Prefer usernames when the endpoint accepts them; resolve URNs with
  `get_profile_overview` when downstream endpoints require a URN.
- Save large raw responses to `/tmp/linkdapi-<purpose>.json` and summarize the
  relevant fields instead of flooding the conversation.
- Treat contact, identity, employment, and recruiting data as sensitive. Return
  only the fields needed for the user's task.
- Handle API-level failures by checking `result.get("success")` and
  `result.get("message")`; handle transport failures with the SDK's documented
  exceptions.

## References

Read [SDK Guide](./references/sdk-guide.md) when you need endpoint groups,
batch/async examples, or official documentation links.
