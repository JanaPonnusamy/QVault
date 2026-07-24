from app.config.knowledge_config import KnowledgeConfig
from app.models.search_source import SearchSource
from app.services.search_providers.base_search_provider import BaseSearchProvider
from app.services.yt_dlp_wrapper import YTDLPWrapper


class YouTubeSearchProvider(BaseSearchProvider):
    """Topic search over YouTube. Reuses the existing YTDLPWrapper (no new
    download tooling) via yt-dlp's ``ytsearchN:`` pseudo-URL, which needs no API key."""

    name = "youtube"

    def search(self, query, limit):
        search_url = f"ytsearch{int(limit)}:{query}"

        # Bias YouTube's own search ranking toward a region/language (gl/hl)
        # instead of polluting the query text — unrelated topics still get
        # their best global match, related ones surface local-language results.
        extra_opts = {}
        country = KnowledgeConfig.search_country()
        lang = KnowledgeConfig.search_lang()

        if country:
            extra_opts["geo_bypass_country"] = country
        if lang:
            extra_opts["extractor_args"] = {"youtube": {"lang": [lang]}}

        info = YTDLPWrapper.extract(search_url, extra_opts=extra_opts)

        entries = (info or {}).get("entries") or []

        sources = []

        for entry in entries:
            if not entry:
                continue

            video_id = entry.get("id") or ""

            if not video_id:
                continue

            url = entry.get("url") or entry.get("webpage_url")

            if not url or not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={video_id}"

            sources.append(
                SearchSource(
                    document_type="youtube_video",
                    source_reference=video_id,
                    title=entry.get("title") or video_id,
                    url=url,
                )
            )

        return sources
