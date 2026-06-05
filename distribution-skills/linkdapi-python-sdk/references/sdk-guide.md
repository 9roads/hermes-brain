---
name: linkdapi-python-sdk-guide
description: Endpoint groups, usage patterns, and official references for the LinkdAPI Python SDK.
---

# LinkdAPI SDK Guide

Hermes has the `linkdapi` package installed in the base image. Use
`LINKD_API_KEY` from the runtime environment.

Official references:

- LinkdAPI docs: https://linkdapi.com/docs/intro
- LinkdAPI API docs: https://linkdapi.com/docs
- Python SDK README: https://github.com/linkdAPI/linkdapi-SDK#readme
- PyPI package: https://pypi.org/project/linkdapi/

## Choosing Sync Or Async

Use sync for single-profile, single-company, and exploratory scripts:

```python
import os
from linkdapi import LinkdAPI

client = LinkdAPI(os.environ["LINKD_API_KEY"])
profile = client.get_profile_overview("ryanroslansky")
```

Use async for batch enrichment or parallel endpoint fan-out:

```python
import asyncio
import os
from linkdapi import AsyncLinkdAPI

async def enrich_usernames(usernames: list[str]) -> list[dict]:
    async with AsyncLinkdAPI(os.environ["LINKD_API_KEY"]) as api:
        tasks = [api.get_profile_overview(username) for username in usernames]
        return await asyncio.gather(*tasks, return_exceptions=True)

results = asyncio.run(enrich_usernames(["ryanroslansky", "satyanadella"]))
```

For large batches, add an `asyncio.Semaphore` and process results
incrementally. Even with SDK retries/throttling, bounded concurrency avoids
waste and makes failures easier to inspect.

## Common Endpoint Groups

Profile:

- `get_profile_overview(username)` for basic profile data.
- `get_profile_details(urn)` for detailed data after resolving a URN.
- `get_contact_info(username)` for contact fields.
- `get_full_profile(username=None, urn=None)` for one-call profile enrichment.
- `get_full_experience(urn)`, `get_education(urn)`, `get_skills(urn)` for
  employment and credential details.

Company:

- `company_name_lookup(query)` to search companies by name.
- `get_company_info(company_id=None, name=None)` for company details.
- `get_company_employees_data(company_id)` for employee statistics.
- `get_company_jobs(company_ids, start=0)` for active job listings.
- `get_similar_companies(company_id)` for competitive/company mapping.

Jobs and market analysis:

- `search_jobs(keyword=None, location=None, company_ids=None, time_posted="any",
  start=0, ...)` for job discovery.
- `get_job_details(job_id)` for a single posting.
- `get_similar_jobs(job_id)` for adjacent roles.

Search and lookup:

- `search_people(...)`, `search_companies(...)`, and `search_posts(...)`.
- `geo_name_lookup(query)`, `title_skills_lookup(query)`, and
  `services_lookup(query)`.
- `get_service_status()` for API availability checks.

## Practical Patterns

For complete profile enrichment:

1. Call `get_full_profile(username=...)` when one response is enough.
2. If more detail is needed, call `get_profile_overview(username)` first and
   read the returned URN.
3. Fan out to URN-based endpoints such as details, experience, education, and
   skills.

For company intelligence:

1. Use `get_company_info(name=...)` or `company_name_lookup(query)` to identify
   the company.
2. Use the returned company ID for employees, jobs, similar companies, and
   affiliated pages.
3. Save raw responses to `/tmp` and return a concise table or JSON subset.

For error handling:

```python
import httpx

try:
    response = client.get_profile_overview("username")
    if not response.get("success"):
        raise RuntimeError(response.get("message", "LinkdAPI request failed"))
except httpx.HTTPStatusError as exc:
    raise RuntimeError(f"LinkdAPI HTTP {exc.response.status_code}") from exc
except httpx.RequestError as exc:
    raise RuntimeError(f"LinkdAPI network error: {exc}") from exc
```
