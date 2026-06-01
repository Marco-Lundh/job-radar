import ssl
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import truststore

from models import Job
from sources.base import BaseJobSource

_API_URL = "https://jobsearch.api.jobtechdev.se/search"
_SSL_CTX = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class PlatsbankenSource(BaseJobSource):
    name = "platsbanken"

    async def search(
        self,
        keywords: Sequence[str],
        location: str | None,
        work_type: Sequence[str],
        max_jobs: int,
    ) -> AsyncIterator[Job]:
        parts = list(keywords)
        if location and not location.strip().isdigit():
            parts.append(location)
        query = " ".join(parts)
        page_size = min(max_jobs, 100)
        params: dict[str, str | int] = {"q": query, "limit": page_size}
        if location and location.strip().isdigit():
            params["municipality"] = location

        # "unknown" always passes — RankerAgent will refine work_type later
        allowed = set(work_type) | {"unknown"} if work_type else None

        yielded = 0
        offset = 0
        async with httpx.AsyncClient(timeout=30, verify=_SSL_CTX) as client:
            while yielded < max_jobs:
                params["offset"] = offset
                resp = await client.get(_API_URL, params=params)
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
                if not hits:
                    break

                for hit in hits:
                    if yielded >= max_jobs:
                        return
                    job = _parse_hit(hit)
                    if allowed is None or job.work_type in allowed:
                        yielded += 1
                        yield job

                if len(hits) < page_size:
                    break
                offset += len(hits)


def _parse_hit(hit: dict[str, object]) -> Job:
    employer = hit.get("employer", {})
    workplace = hit.get("workplace_address", {})
    desc_raw = hit.get("description", {})
    desc_text = desc_raw.get("text", "") if isinstance(desc_raw, dict) else ""

    work_type = "unknown"
    wh = hit.get("working_hours_type")
    wh_label = (wh.get("label", "") if isinstance(wh, dict) else "").lower()
    if wh_label == "distansarbete":
        work_type = "remote"
    elif "hybrid" in desc_text.lower():
        work_type = "hybrid"
    elif desc_text:
        work_type = "on-site"

    def s(val: object) -> str:
        return val if isinstance(val, str) else ""

    return Job(
        id=hit.get("id") or str(uuid4()),
        source="platsbanken",
        title=s(hit.get("headline")),
        company=s(employer.get("name")),
        location=(
            s(workplace.get("municipality")) or s(workplace.get("region"))
        ),
        work_type=work_type,
        description=desc_text,
        url=s(hit.get("webpage_url")),
        posted_date=hit.get("publication_date"),
        scraped_at=datetime.now(UTC).isoformat(),
    )
