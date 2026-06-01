from collections.abc import AsyncIterator

import storage
from agents._utils import _sse
from models import SearchConfig
from sources.platsbanken import PlatsbankenSource


async def run_scraper_agent(config: SearchConfig) -> AsyncIterator[str]:
    sources = {
        "platsbanken": PlatsbankenSource(),
    }

    existing_ids = {j.id for j in storage.load_jobs()}
    total_new = 0
    for source_cfg in config.sources:
        if not source_cfg.enabled:
            continue
        source = sources.get(source_cfg.name)
        if not source:
            yield _sse(
                {
                    "type": "error",
                    "message": f"Unknown source: {source_cfg.name}",
                }
            )
            continue

        query = " ".join(config.keywords)
        yield _sse(
            {
                "type": "progress",
                "message": (
                    f"Searching {source_cfg.name} — "
                    f"query: '{query}', max: {config.max_jobs}"
                ),
            }
        )
        new_count = 0
        new_jobs = []
        try:
            async for job in source.search(
                keywords=config.keywords,
                location=config.location,
                work_type=config.work_type,
                max_jobs=config.max_jobs,
            ):
                if job.id in existing_ids:
                    continue
                new_jobs.append(job)
                existing_ids.add(job.id)
                new_count += 1
                total_new += 1
                yield _sse(
                    {
                        "type": "progress",
                        "message": f"Found: {job.title} at {job.company}",
                    }
                )
        except Exception as exc:
            yield _sse(
                {
                    "type": "error",
                    "message": f"{source_cfg.name} error: {exc}",
                }
            )
        if new_jobs:
            storage.batch_upsert_jobs(new_jobs)

        yield _sse(
            {
                "type": "progress",
                "message": f"{source_cfg.name}: {new_count} new jobs added.",
            }
        )

    yield _sse({"type": "done", "new_jobs": total_new})
