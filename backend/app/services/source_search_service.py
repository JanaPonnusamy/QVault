from app.services.search_providers.youtube_search_provider import (
    YouTubeSearchProvider,
)


class SourceSearchService:
    """Single entrypoint for topic search. Business logic calls
    ``SourceSearchService.search(...)`` and stays independent of the provider.
    Add a provider (PDF corpus, web, arXiv, ...) by registering it below."""

    _PROVIDERS = {
        "youtube": YouTubeSearchProvider,
    }

    def __init__(self, source_type="youtube"):
        provider_cls = self._PROVIDERS.get(source_type)

        if provider_cls is None:
            raise RuntimeError(
                f"Unknown search source '{source_type}'. "
                f"Available: {', '.join(self._PROVIDERS)}"
            )

        self.source_type = source_type
        self._provider = provider_cls()

    def search(self, query, limit):
        return self._provider.search(query, limit)
