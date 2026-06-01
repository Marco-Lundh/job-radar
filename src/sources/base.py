from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from models import Job


class BaseJobSource(ABC):
    name: str

    @abstractmethod
    def search(
        self,
        keywords: Sequence[str],
        location: str | None,
        work_type: Sequence[str],
        max_jobs: int,
    ) -> AsyncIterator[Job]: ...
