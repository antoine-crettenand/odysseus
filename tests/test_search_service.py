"""Tests for SearchService release search and conversion behavior."""

from unittest.mock import MagicMock

from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.search_results import DiscogsRelease, MusicBrainzSong
from odysseus.models.song import SongData

def _release(album, release_type="Album", source="musicbrainz", mbid="id"):
    return MusicBrainzSong(
        title=album,
        artist="Artist",
        album=album,
        release_type=release_type,
        mbid=mbid,
        source=source,
    )

def _search_service(mb_results, *, spotify_results=None, max_results=3):
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=max_results)
    service.musicbrainz_client.search_release.return_value = mb_results
    service.discogs_client = MagicMock()
    service.discogs_client.search_release.return_value = []
    service._spotify_client = None
    if spotify_results is not None:
        service._spotify_client = MagicMock()
        service._spotify_client.is_authenticated.return_value = True
        service._spotify_client.search_release.return_value = spotify_results
    service.deduplicator = ResultDeduplicator()
    return service

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

def test_release_search_applies_default_limit():
    service = _search_service(
        [_release(f"Album {index}", mbid=str(index)) for index in range(9)]
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Album")
    )

    assert len(results) == 3

def test_release_type_is_filtered_before_provider_deduplication():
    ep = _release("Shared Title", release_type="EP", mbid="ep")
    service = _search_service(
        [ep],
        spotify_results=[
            {
                "album": "Shared Title",
                "artist": "Artist",
                "release_type": "album",
                "spotify_id": "wrong-type",
            }
        ],
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Shared Title"),
        release_type="EP",
    )

    assert [result.mbid for result in results] == ["ep"]
    assert service.musicbrainz_client.search_release.call_args.args[3] == "EP"

def test_recording_dedup_keeps_distinct_titles_on_same_album():
    deduplicator = ResultDeduplicator()
    results = [
        MusicBrainzSong(
            title="Song A",
            artist="Artist",
            album="Same Album",
            source="musicbrainz",
        ),
        MusicBrainzSong(
            title="Song B",
            artist="Artist",
            album="Same Album",
            source="musicbrainz",
        ),
    ]

    deduped = deduplicator.deduplicate_results(results, recordings=True)

    assert len(deduped) == 2
    assert {song.title for song in deduped} == {"Song A", "Song B"}
