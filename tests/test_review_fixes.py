"""Regression tests for defects found in the refactor review."""

from unittest.mock import MagicMock, patch

import pytest

from odysseus.clients.base_api_client import BaseAPIClient
from odysseus.clients.discogs import (
    extract_discogs_physical_format,
    extract_discogs_release_type,
)
from odysseus.core.http import HttpClient
from odysseus.core.validation.input_validators import validate_year
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.search_results import DiscogsRelease, MusicBrainzSong
from odysseus.ui.handlers.recording_handler import RecordingHandler
from odysseus.models.search_results import YouTubeVideo


def test_include_compilations_uses_deduplicator_keys():
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock()
    service.musicbrainz_client.search_artist_releases.return_value = []
    existing = MusicBrainzSong(
        title="Album",
        artist="Artist",
        album="Album",
        source="musicbrainz",
    )
    compilation = MusicBrainzSong(
        title="Comp Track",
        artist="Artist",
        album="Various",
        release_type="Compilation",
        source="musicbrainz",
    )
    service.musicbrainz_client.search_artist_compilations.return_value = [compilation]
    service.deduplicator = MagicMock()
    service.deduplicator.deduplicate_results.return_value = [existing]
    service.deduplicator._create_deduplication_key.side_effect = (
        lambda r: (r.album or r.title, r.artist)
    )
    service._deduplicate_results = service.deduplicator.deduplicate_results

    results = service.search_artist_releases("Artist", include_compilations=True)

    assert existing in results
    assert compilation in results
    assert service.deduplicator._create_deduplication_key.call_count >= 2


def test_discogs_release_type_prefers_logical_type_over_medium():
    assert extract_discogs_release_type(["Vinyl", "LP", "Album"]) == "Album"
    assert extract_discogs_physical_format(["Vinyl", "LP", "Album"]) == "Vinyl"
    assert extract_discogs_release_type(
        [{"name": "Vinyl", "descriptions": ["Album", "LP"]}]
    ) == "Album"


def test_discogs_to_mb_conversion_uses_release_type_not_format():
    service = SearchService.__new__(SearchService)
    discogs = DiscogsRelease(
        title="Album",
        artist="Artist",
        album="Album",
        format="Vinyl",
        release_type="Album",
        discogs_id="123",
        source="discogs",
    )

    converted = service._convert_discogs_to_mb_format([discogs])

    assert converted[0].release_type == "Album"


def test_validate_year_raises_for_out_of_range():
    with pytest.raises(ValueError, match="between"):
        validate_year(1800)


def test_validate_year_can_coerce_out_of_range():
    assert validate_year(1800, coerce=True) is None
    assert validate_year(2020) == 2020


def test_http_client_paces_successful_requests_between_calls():
    first = MagicMock()
    first.status_code = 200
    first.raise_for_status = MagicMock()
    second = MagicMock()
    second.status_code = 200
    second.raise_for_status = MagicMock()

    session = MagicMock()
    session.get.side_effect = [first, second]
    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    client = HttpClient(
        session_manager=session_manager,
        default_request_delay=0.5,
    )

    with patch(
        "odysseus.core.http.http_client.time.monotonic",
        side_effect=[
            10.0,  # stamp after first request
            10.1,  # pacing check before second request
            10.6,  # stamp after second request
        ],
    ):
        with patch("odysseus.core.http.http_client.time.sleep") as sleep:
            client.get("https://example.test/a", max_retries=0)
            client.get("https://example.test/b", max_retries=0)

    sleep.assert_called_once()
    assert sleep.call_args.args[0] == pytest.approx(0.4)


def test_empty_search_results_are_not_cached():
    cache = MagicMock()
    cache.get.return_value = None
    cache_manager = MagicMock()
    cache_manager.get_cache.return_value = cache
    client = BaseAPIClient(
        {
            "BASE_URL": "https://example.test",
            "USER_AGENT": "test",
            "REQUEST_DELAY": 0,
            "MAX_RESULTS": 10,
            "TIMEOUT": 5,
        },
        cache_manager=cache_manager,
        http_client=MagicMock(),
    )

    result = client._get_cached_or_fetch("search", "key", lambda: [])

    assert result == []
    cache.set.assert_not_called()


def test_recording_reshuffle_wraps_when_offset_exhausted():
    first_batch = [
        YouTubeVideo(title="First", artist="Artist", video_id="1"),
    ]
    selected_video = YouTubeVideo(title="Again", artist="Artist", video_id="1")
    batches = iter((first_batch, [], [selected_video]))

    handler = RecordingHandler.__new__(RecordingHandler)
    handler.search_service = MagicMock()
    handler.display_manager = MagicMock()
    handler.display_manager.show_loading_spinner.side_effect = (
        lambda _message, function, *args: (
            function(*args),
            next(batches),
        )[1]
    )
    handler.display_manager.get_video_selection.side_effect = (
        "RESHUFFLE",
        selected_video,
    )
    handler.release_validator = MagicMock()
    handler.release_validator.extract_release_year.return_value = 2020
    handler.download_orchestrator = MagicMock()

    selected_song = MagicMock(
        artist="Artist",
        title="Title",
        album="Album",
        release_date="2020",
    )

    handler._search_and_download_recording(selected_song, "audio")

    assert handler.search_service.search_youtube.call_args_list == [
        (("Artist Title", 3, 0),),
        (("Artist Title", 3, 1),),
        (("Artist Title", 3, 0),),
    ]
    handler.download_orchestrator.download_recording.assert_called_once()


def test_release_pagination_fetches_enough_candidates_for_offset():
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=3)
    service.musicbrainz_client.search_release.return_value = []
    service.discogs_client = MagicMock()
    service.discogs_client.search_release.return_value = []
    service._spotify_client = None
    service._deduplicate_with_priority = lambda left, right: left + right
    service._convert_discogs_to_mb_format = lambda results: []

    service.search_releases(
        MagicMock(album="Album", artist="Artist", release_year=None),
        offset=6,
        limit=3,
    )

    assert service.musicbrainz_client.search_release.call_args.args[2] == 27
    assert service.discogs_client.search_release.call_args.args[2] == 27
