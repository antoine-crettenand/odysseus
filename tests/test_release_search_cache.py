"""Regression tests for reusable release-search snapshots."""

from unittest.mock import MagicMock

from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.search_results import MusicBrainzSong
from odysseus.models.song import SongData


def _release(name, release_type="Album", mbid=None):
    return MusicBrainzSong(
        title=name,
        artist="Artist",
        album=name,
        release_date="2000",
        original_release_date="2000",
        release_type=release_type,
        mbid=mbid or name.casefold().replace(" ", "-"),
        source="musicbrainz",
    )


def _service(results_by_type):
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=3)
    service.musicbrainz_client.search_release.side_effect = (
        lambda _song, _offset, _limit, release_type: list(
            results_by_type.get(release_type, [])
        )
    )
    service.discogs_client = MagicMock()
    service.discogs_client.search_release.return_value = []
    service._spotify_client = None
    service._apple_music_client = None
    service.deduplicator = ResultDeduplicator()
    return service


def _query():
    return SongData(title="", artist="Artist", album="Release")


def test_all_types_snapshot_serves_album_refinement_without_provider_calls():
    albums = [_release(f"Album {index}") for index in range(3)]
    service = _service(
        {
            None: [*albums, _release("An EP", "EP")],
            "Album": albums,
        }
    )
    service._spotify_client = MagicMock()
    service._spotify_client.is_authenticated.return_value = True
    service._spotify_client.search_release.return_value = [
        {
            "album": "Spotify Album",
            "artist": "Artist",
            "release_type": "album",
            "spotify_id": "spotify-album",
        }
    ]
    service._apple_music_client = MagicMock(storefront="ch")
    service._apple_music_client.is_authenticated.return_value = True
    service._apple_music_client.search_release.return_value = [
        {
            "id": "apple-album",
            "album": "Apple Album",
            "artist": "Artist",
            "release_type": "Album",
        }
    ]

    service.search_releases(_query(), limit=2)
    results = service.search_releases(
        _query(), limit=2, release_type="Album"
    )

    assert [result.album for result in results] == ["Album 0", "Album 1"]
    assert service.musicbrainz_client.search_release.call_count == 1
    assert service.discogs_client.search_release.call_count == 1
    assert service._spotify_client.search_release.call_count == 1
    assert service._apple_music_client.search_release.call_count == 1
    assert service.musicbrainz_client.search_release.call_args.args[3] is None


def test_narrow_snapshot_does_not_serve_all_types_query():
    albums = [_release(f"Album {index}") for index in range(3)]
    service = _service(
        {
            "Album": albums,
            None: [*albums, _release("An EP", "EP")],
        }
    )

    service.search_releases(_query(), limit=2, release_type="Album")
    service.search_releases(_query(), limit=2)

    assert service.musicbrainz_client.search_release.call_count == 2
    assert [
        call.args[3]
        for call in service.musicbrainz_client.search_release.call_args_list
    ] == ["Album", None]


def test_incomplete_broad_page_falls_back_to_type_specific_search():
    service = _service(
        {
            None: [_release("Only Album"), _release("An EP", "EP")],
            "Album": [_release("Only Album"), _release("Another Album")],
        }
    )

    service.search_releases(_query(), limit=2)
    results = service.search_releases(
        _query(), limit=2, release_type="Album"
    )

    assert [result.album for result in results] == [
        "Only Album",
        "Another Album",
    ]
    assert service.musicbrainz_client.search_release.call_count == 2
    assert service.musicbrainz_client.search_release.call_args.args[3] == "Album"


def test_cached_snapshot_is_not_modified_through_returned_results():
    service = _service({None: [_release("Original Name")]})

    first_results = service.search_releases(_query(), limit=1)
    first_results[0].album = "Changed by UI"

    second_results = service.search_releases(_query(), limit=1)

    assert second_results[0].album == "Original Name"
    assert service.musicbrainz_client.search_release.call_count == 1


def test_cache_key_normalizes_harmless_query_casing_and_spacing():
    service = _service({None: [_release("Original Name")]})

    service.search_releases(_query(), limit=1)
    service.search_releases(
        SongData(title="", artist="  ARTIST  ", album=" release "),
        limit=1,
    )

    assert service.musicbrainz_client.search_release.call_count == 1
