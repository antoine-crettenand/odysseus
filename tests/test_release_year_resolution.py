"""Regression tests for original-versus-edition release years."""

from unittest.mock import MagicMock

from odysseus.clients.discogs import DiscogsClient
from odysseus.domain.music.common.date_utils import (
    format_release_date_label,
    release_year_in_range,
)
from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.search.search_service import SearchService
from odysseus.domain.music.validation.year_validator import YearValidator
from odysseus.models.search_results import DiscogsRelease, MusicBrainzSong
from odysseus.models.song import SongData


def _catalog_service(musicbrainz_results, spotify_results):
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=10)
    service.musicbrainz_client.search_release.return_value = musicbrainz_results
    service.discogs_client = MagicMock()
    service.discogs_client.search_release.return_value = []
    service._spotify_client = MagicMock()
    service._spotify_client.is_authenticated.return_value = True
    service._spotify_client.search_release.return_value = spotify_results
    service.deduplicator = ResultDeduplicator()
    return service


def test_musicbrainz_original_year_wins_over_spotify_reissue():
    original = MusicBrainzSong(
        title="Album",
        artist="Artist",
        album="Album",
        release_date="2021-06-01",
        original_release_date="1971-03-19",
        release_type="Album",
        mbid="musicbrainz-id",
        source="musicbrainz",
    )
    service = _catalog_service(
        [original],
        [
            {
                "album": "Album",
                "artist": "Artist",
                "release_date": "2021-06-01",
                "release_year": 2021,
                "release_type": "Album",
                "spotify_id": "spotify-reissue",
            }
        ],
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Album"), limit=10
    )

    assert [(result.source, result.mbid) for result in results] == [
        ("musicbrainz", "musicbrainz-id")
    ]


def test_spotify_date_is_not_claimed_as_an_original_date():
    service = SearchService.__new__(SearchService)

    converted = service._convert_spotify_to_mb_format(
        [
            {
                "album": "Album",
                "artist": "Artist",
                "release_date": "2021-06-01",
                "spotify_id": "spotify-id",
            }
        ]
    )

    assert converted[0].release_date == "2021-06-01"
    assert converted[0].original_release_date is None


def test_original_year_drives_ranges_and_dates_show_the_edition():
    reissue = MusicBrainzSong(
        title="Album",
        artist="Artist",
        album="Album",
        release_date="2021-06-01",
        original_release_date="1971-03-19",
    )

    assert release_year_in_range(reissue, 1970, 1980) is True
    assert release_year_in_range(reissue, 2020, 2022) is False
    assert format_release_date_label(reissue) == (
        "1971-03-19 · edition 2021-06-01"
    )


def test_year_validator_rejects_unrelated_first_results():
    spotify = MagicMock(access_token="token")
    spotify.search_items.return_value = [
        {
            "name": "Different Album",
            "artists": [{"name": "Different Artist"}],
            "release_date": "1960",
        }
    ]
    discogs = MagicMock()
    discogs.search_release.return_value = [
        DiscogsRelease(
            title="Different Album",
            album="Different Album",
            artist="Different Artist",
            year=1950,
        )
    ]
    validator = YearValidator(lambda: spotify, discogs)

    assert validator.get_release_year("Artist", "Album") is None


def test_discogs_master_year_beats_conflicting_spotify_edition_year():
    spotify = MagicMock(access_token="token")
    spotify.search_items.return_value = [
        {
            "name": "Album",
            "artists": [{"name": "Artist"}],
            "release_date": "2021-06-01",
        }
    ]
    discogs = MagicMock()
    discogs.search_release.return_value = [
        DiscogsRelease(
            title="Album",
            album="Album",
            artist="Artist (2)",
            year=2021,
            master_id="42",
        )
    ]
    discogs.get_master_year.return_value = 1971
    validator = YearValidator(lambda: spotify, discogs)

    assert validator.get_release_year("Artist", "Album") == 1971
    assert validator.validate_year("Artist", "Album", [1971, 2021]) == 1971


def test_discogs_details_preserve_master_and_edition_years():
    client = DiscogsClient.__new__(DiscogsClient)
    client.get_master_year = MagicMock(return_value=1971)

    release = client._parse_release_info(
        {
            "id": 1,
            "master_id": 42,
            "title": "Album",
            "year": 2021,
            "artists": [{"name": "Artist"}],
            "tracklist": [],
        }
    )

    assert release.release_date == "2021"
    assert release.original_release_date == "1971"


def test_discogs_master_year_uses_the_master_endpoint_and_cache_boundary():
    client = DiscogsClient.__new__(DiscogsClient)
    client.base_url = "https://api.discogs.test"
    client._generate_release_info_cache_key = MagicMock(return_value="key")
    client._make_request = MagicMock(return_value={"year": 1971})
    client._get_cached_or_fetch = MagicMock(
        side_effect=lambda _cache, _key, fetch: fetch()
    )

    assert client.get_master_year("42") == 1971
    client._make_request.assert_called_once_with(
        "https://api.discogs.test/masters/42", {}
    )
    client._get_cached_or_fetch.assert_called_once()


def test_deduplication_does_not_invent_an_original_year():
    first_edition = MusicBrainzSong(
        title="Album",
        artist="Artist",
        album="Album",
        release_date="1971",
        mbid="first",
    )
    reissue = MusicBrainzSong(
        title="Album",
        artist="Artist",
        album="Album",
        release_date="2021",
        mbid="reissue",
    )

    selected = ResultDeduplicator().deduplicate_results(
        [reissue, first_edition]
    )

    assert selected[0].mbid == "first"
    assert first_edition.original_release_date is None
    assert reissue.original_release_date is None
