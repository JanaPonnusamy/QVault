from typing import List

from app.models.search_source import SearchSource


class BaseSearchProvider:
    """Search provider interface. Providers turn a topic query into a list of
    SearchSource records so the extraction pipeline stays source-agnostic."""

    name = "base"

    def search(self, query: str, limit: int) -> List[SearchSource]:
        raise NotImplementedError
