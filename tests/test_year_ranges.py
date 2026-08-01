"""Regression tests for inclusive release-year range filtering."""

from unittest.mock import MagicMock

import pytest

from odysseus.core.validation import validate_year_range
from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.outcomes import OperationOutcome
from odysseus.models.search_results import MusicBrainzSong
from odysseus.models.song import SongData
from odysseus.ui.cli import OdysseusCLI


def _release(album, year, *, source="musicbrainz", mbid=None):
    return MusicBrainzSong(
        title=album,
        artist="Artist",
        album=album,
        release_date=str(year),
        original_release_date=str(year),
        release_type="Album",
        mbid=mbid or f"{source}-{year}",
        source=source,
    )


def _service(mb_results, spotify_results=None):
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock(max_results=10)
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


def test_year_range_validation_supports_exact_bounded_and_open_ranges():
    assert validate_year_range(1975) == (1975, 1975)
    assert validate_year_range(year_from=1970, year_to=1980) == (1970, 1980)
    assert validate_year_range(year_from=1970) == (1970, None)
    assert validate_year_range(year_to=1980) == (None, 1980)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"year": 1975, "year_from": 1970},
        {"year_from": 1980, "year_to": 1970},
        {"year_from": 1800},
    ],
)
def test_year_range_validation_rejects_conflicts_and_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        validate_year_range(**kwargs)


def test_cli_forwards_release_year_range():
    cli = OdysseusCLI(load_services=False)
    cli.release_handler = MagicMock()
    cli.release_handler.handle.return_value = OperationOutcome.success()
    cli.display_manager = MagicMock()

    exit_code = cli.run(
        [
            "release",
            "--album",
            "Album",
            "--artist",
            "Artist",
            "--year-from",
            "1970",
            "--year-to",
            "1980",
            "--no-download",
        ]
    )

    assert exit_code == 0
    assert cli.release_handler.handle.call_args.kwargs["year_from"] == 1970
    assert cli.release_handler.handle.call_args.kwargs["year_to"] == 1980


def test_cli_rejects_exact_year_combined_with_range():
    cli = OdysseusCLI(load_services=False)

    with pytest.raises(SystemExit) as error:
        cli.run(
            [
                "release",
                "--album",
                "Album",
                "--artist",
                "Artist",
                "--year",
                "1975",
                "--year-from",
                "1970",
            ]
        )

    assert error.value.code == 2


def test_release_range_is_inclusive_and_filters_before_deduplication():
    in_range = _release("Shared Album", 1970, mbid="in-range")
    service = _service(
        [in_range, _release("Upper Boundary", 1980)],
        spotify_results=[
            {
                "album": "Shared Album",
                "artist": "Artist",
                "release_type": "album",
                "release_date": "1990",
                "release_year": 1990,
                "spotify_id": "out-of-range",
            }
        ],
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Album"),
        limit=10,
        year_from=1970,
        year_to=1980,
    )

    assert {result.mbid for result in results} == {
        "in-range",
        "musicbrainz-1980",
    }
    assert service.musicbrainz_client.search_release.call_args.args[2] == 50


@pytest.mark.parametrize(
    ("year_from", "year_to", "expected"),
    [
        (1975, None, {1975, 1980}),
        (None, 1975, {1970, 1975}),
    ],
)
def test_release_search_supports_open_ended_ranges(
    year_from,
    year_to,
    expected,
):
    service = _service(
        [
            _release("Early", 1970),
            _release("Middle", 1975),
            _release("Late", 1980),
        ]
    )

    results = service.search_releases(
        SongData(title="", artist="Artist", album="Album"),
        limit=10,
        year_from=year_from,
        year_to=year_to,
    )

    assert {int(result.release_date) for result in results} == expected


def test_discography_range_filters_releases_and_compilations():
    service = SearchService.__new__(SearchService)
    service.musicbrainz_client = MagicMock()
    service.musicbrainz_client.search_artist_releases.return_value = [
        _release("Too Early", 1969),
        _release("Lower Boundary", 1970),
        _release("Upper Boundary", 1980),
        _release("Too Late", 1981),
    ]
    compilation = _release("Compilation", 1975)
    compilation.release_type = "Compilation"
    service.musicbrainz_client.search_artist_compilations.return_value = [
        compilation
    ]
    service.deduplicator = ResultDeduplicator()

    results = service.search_artist_releases(
        "Artist",
        include_compilations=True,
        year_from=1970,
        year_to=1980,
    )

    assert {result.album for result in results} == {
        "Lower Boundary",
        "Upper Boundary",
        "Compilation",
    }
    service.musicbrainz_client.search_artist_releases.assert_called_once_with(
        "Artist",
        None,
        None,
        None,
    )


def test_batch_rows_with_exact_year_override_global_range():
    cli = OdysseusCLI.__new__(OdysseusCLI)
    cli.display_manager = MagicMock()
    cli._parse_batch_file = MagicMock(
        return_value=[
            ("Artist", "Exact", 1965),
            ("Artist", "Ranged", None),
        ]
    )
    cli.release_handler = MagicMock()
    cli.release_handler.handle.return_value = OperationOutcome.success()

    outcome = cli._handle_batch_release(
        "batch.tsv",
        release_type=None,
        quality="audio",
        tracks=None,
        no_download=True,
        year_from=1970,
        year_to=1980,
    )

    assert outcome.succeeded is True
    exact_call, ranged_call = cli.release_handler.handle.call_args_list
    assert exact_call.kwargs["year"] == 1965
    assert exact_call.kwargs["year_from"] is None
    assert exact_call.kwargs["year_to"] is None
    assert ranged_call.kwargs["year"] is None
    assert ranged_call.kwargs["year_from"] == 1970
    assert ranged_call.kwargs["year_to"] == 1980
