"""
Service registration for dependency injection container.
Registers all services, clients, and handlers with their dependencies.
"""

from typing import Callable, Any
from .container import Container
from ...clients.network_agent import NetworkAgent
from ...core.config import MUSICBRAINZ_CONFIG


def _register_simple(container: Container, name: str, import_func: Callable[[], Any]) -> None:
    """Register a simple service with no dependencies."""
    container.register(name, import_func, singleton=True)


def _register_handler(container: Container, name: str, handler_factory: Callable[[], Any]) -> None:
    """Register a handler with standard dependencies."""
    container.register(name, handler_factory, singleton=True)


def register_all_services(container: Container) -> None:
    """Register all services, clients, and handlers in the container."""
    # Core infrastructure — use MusicBrainz UA (includes required contact info)
    container.register("network_agent",
        lambda: NetworkAgent(MUSICBRAINZ_CONFIG["USER_AGENT"]),
        singleton=True)

    def create_http_client():
        from ..http import HttpClient, SessionManager
        network_agent = container.get("network_agent")
        return HttpClient(
            session_manager=SessionManager(network_agent=network_agent),
            network_agent=network_agent,
            default_request_delay=MUSICBRAINZ_CONFIG["REQUEST_DELAY"],
            default_timeout=MUSICBRAINZ_CONFIG["TIMEOUT"],
        )
    container.register("http_client", create_http_client, singleton=True)

    # Simple clients and services
    def create_cache_manager():
        from ..cache import CacheManager
        return CacheManager()
    _register_simple(container, "cache_manager", create_cache_manager)

    def create_musicbrainz_client():
        from ...clients.musicbrainz import MusicBrainzClient
        return MusicBrainzClient(
            cache_manager=container.get("cache_manager"),
            http_client=container.get("http_client")
        )
    container.register("musicbrainz_client", create_musicbrainz_client, singleton=True)

    def create_discogs_client():
        from ...clients.discogs import DiscogsClient
        return DiscogsClient(
            cache_manager=container.get("cache_manager"),
            http_client=container.get("http_client")
        )
    container.register("discogs_client", create_discogs_client, singleton=True)

    from ...clients.youtube import YouTubeClient
    container.register_instance(
        "youtube_client_factory",
        lambda query, max_results=None: YouTubeClient(
            query,
            max_results,
            http_client=container.get("http_client"),
        ),
    )

    def create_spotify_client():
        from ...clients.spotify import SpotifyClient
        return SpotifyClient(http_client=container.get("http_client"))
    _register_simple(container, "spotify_client", create_spotify_client)

    def create_download_service():
        from ...domain.music.download.download_service import DownloadService
        return DownloadService()
    _register_simple(container, "download_service", create_download_service)

    def create_duration_recovery():
        from ...domain.music.metadata.duration_recovery import DurationRecoveryService
        return DurationRecoveryService(
            musicbrainz_client=container.get("musicbrainz_client"),
            spotify_client=container.get("spotify_client"),
            discogs_client=container.get("discogs_client"),
        )
    container.register("duration_recovery", create_duration_recovery, singleton=True)

    def create_display_manager():
        from ...ui.display import DisplayManager
        return DisplayManager(duration_recovery=container.get("duration_recovery"))
    _register_simple(container, "display_manager", create_display_manager)

    # Services with dependencies
    def create_search_service():
        from ...domain.music.search.search_service import SearchService
        return SearchService(
            musicbrainz_client=container.get("musicbrainz_client"),
            discogs_client=container.get("discogs_client"),
            youtube_client_factory=container.get("youtube_client_factory"),
            spotify_client=container.get("spotify_client"),
        )
    container.register("search_service", create_search_service, singleton=True)

    def create_cover_art_fetcher():
        from ...domain.media.cover_art.fetcher import CoverArtFetcher
        return CoverArtFetcher(
            network_agent=container.get("network_agent"),
            cache_manager=container.get("cache_manager"),
            http_client=container.get("http_client"),
            musicbrainz_client=container.get("musicbrainz_client"),
            discogs_client=container.get("discogs_client"),
            spotify_client=container.get("spotify_client"),
        )
    container.register("cover_art_fetcher", create_cover_art_fetcher, singleton=True)

    def create_metadata_service():
        from ...domain.music.metadata.metadata_service import MetadataService
        return MetadataService(cover_art_fetcher=container.get("cover_art_fetcher"))
    container.register("metadata_service", create_metadata_service, singleton=True)

    def create_download_orchestrator():
        from ...domain.music.download.orchestrator import DownloadOrchestrator
        return DownloadOrchestrator(download_service=container.get("download_service"),
                                   metadata_service=container.get("metadata_service"),
                                   search_service=container.get("search_service"),
                                   display_manager=container.get("display_manager"))
    container.register("download_orchestrator", create_download_orchestrator, singleton=True)

    def _handler_kwargs():
        return dict(
            search_service=container.get("search_service"),
            download_service=container.get("download_service"),
            metadata_service=container.get("metadata_service"),
            display_manager=container.get("display_manager"),
            download_orchestrator=container.get("download_orchestrator"),
        )

    # Handlers (all have same dependencies)
    def create_recording_handler():
        from ...ui.handlers.recording_handler import RecordingHandler
        return RecordingHandler(**_handler_kwargs())
    _register_handler(container, "recording_handler", create_recording_handler)

    def create_release_handler():
        from ...ui.handlers.release_handler import ReleaseHandler
        return ReleaseHandler(**_handler_kwargs())
    _register_handler(container, "release_handler", create_release_handler)

    def create_discography_handler():
        from ...ui.handlers.discography_handler import DiscographyHandler
        return DiscographyHandler(**_handler_kwargs())
    _register_handler(container, "discography_handler", create_discography_handler)

    def create_metadata_handler():
        from ...ui.handlers.metadata_handler import MetadataHandler
        return MetadataHandler(**_handler_kwargs())
    _register_handler(container, "metadata_handler", create_metadata_handler)

    def create_spotify_handler():
        from ...ui.handlers.spotify_handler import SpotifyHandler
        return SpotifyHandler(
            **_handler_kwargs(),
            spotify_client=container.get("spotify_client"),
            release_handler=container.get("release_handler"),
        )
    _register_handler(container, "spotify_handler", create_spotify_handler)
