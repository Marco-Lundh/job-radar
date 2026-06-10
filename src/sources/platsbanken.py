import ssl
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from typing import Literal
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


WorkType = Literal["remote", "hybrid", "on-site", "unknown"]

# Platsbanken marks fully remote roles with this working-hours label.
_REMOTE_LABEL = "distansarbete"
# Hybrid roles are only discoverable from free-text in the description.
_HYBRID_KEYWORD = "hybrid"


def _text(node: object, *keys: str) -> str:
    """Walk a nested JSON path, returning "" for any missing/None step."""
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, str) else ""


def _detect_work_type(label: str, description: str) -> WorkType:
    if label.lower() == _REMOTE_LABEL:
        return "remote"
    if _HYBRID_KEYWORD in description.lower():
        return "hybrid"
    if description:
        return "on-site"
    return "unknown"


def _parse_hit(hit: dict[str, object]) -> Job:
    description = _text(hit, "description", "text")
    work_type = _detect_work_type(
        _text(hit, "working_hours_type", "label"), description
    )

    return Job(
        id=_text(hit, "id") or str(uuid4()),
        source="platsbanken",
        title=_text(hit, "headline"),
        company=_text(hit, "employer", "name"),
        location=_text(hit, "workplace_address", "municipality")
        or _text(hit, "workplace_address", "region"),
        work_type=work_type,
        description=description,
        url=_text(hit, "webpage_url"),
        posted_date=_text(hit, "publication_date") or None,
        scraped_at=datetime.now(UTC).isoformat(),
    )
