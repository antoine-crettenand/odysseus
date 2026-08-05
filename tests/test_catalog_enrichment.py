"""Coverage for optional catalog enrichment and audio verification."""

from pathlib import Path
from types import SimpleNamespace

from odysseus.clients.acoustid import AcoustIDClient
from odysseus.clients.apple_music import AppleMusicClient
from odysseus.clients.musicbrainz import MusicBrainzClient
from odysseus.domain.music.search.search_service import SearchService
from odysseus.models.song import SongData


class JsonHttpStub:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get_json(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class EmptyCatalogStub:
    max_results = 3

    def search_release(self, *args, **kwargs):
        return []

    def get_release_info(self, *args, **kwargs):
        return None


class AppleCatalogStub:
    def __init__(self):
        self.search_calls = []
        self.info = object()

    def is_authenticated(self):
        return True

    def search_release(self, **kwargs):
        self.search_calls.append(kwargs)
        return [
            {
                "id": "apple-id",
                "album": "Meddle",
                "artist": "Pink Floyd",
                "release_date": "2016-01-01",
                "release_type": "Album",
                "barcode": "190295996483",
            }
        ]

    def get_album_tracks(self, album_id):
        assert album_id == "apple-id"
        return self.info


class DeduplicatorStub:
    def deduplicate_with_priority(self, primary, secondary):
        return list(primary) + list(secondary)

    def deduplicate_results(self, results, release_type=None, recordings=False):
        return list(results)


class YearValidatorStub:
    def resolve_discogs_year(self, *args):
        return None


def test_musicbrainz_release_parser_exposes_edition_metadata():
    client = MusicBrainzClient.__new__(MusicBrainzClient)
    results = client._parse_release_results(
        {
            "releases": [
                {
                    "id": "release-id",
                    "title": "Meddle",
                    "date": "1971-11-05",
                    "country": "GB",
                    "status": "Official",
                    "barcode": "077774603425",
                    "track-count": 6,
                    "artist-credit": [{"name": "Pink Floyd"}],
                    "release-group": {
                        "primary-type": "Album",
                        "first-release-date": "1971-10-30",
                    },
                    "label-info": [
                        {
                            "catalog-number": "SHVL 795",
                            "label": {"name": "Harvest"},
                        }
                    ],
                    "media": [{"format": "12\" Vinyl", "track-count": 6}],
                }
            ]
        }
    )

    release = results[0]
    assert release.country == "GB"
    assert release.release_status == "Official"
    assert release.label == "Harvest"
    assert release.catalog_number == "SHVL 795"
    assert release.barcode == "077774603425"
    assert release.media_format == '12" Vinyl'
    assert release.track_count == 6


def test_apple_music_search_keeps_only_exact_album_artist_matches():
    http = JsonHttpStub(
        [
            {
                "results": {
                    "albums": {
                        "data": [
                            {
                                "id": "good",
                                "attributes": {
                                    "name": "Meddle",
                                    "artistName": "Pink Floyd",
                                    "releaseDate": "2016-01-01",
                                    "trackCount": 6,
                                    "upc": "190295996483",
                                    "recordLabel": "Pink Floyd Records",
                                    "genreNames": ["Rock"],
                                    "artwork": {
                                        "url": "https://img/{w}x{h}.jpg"
                                    },
                                },
                            },
                            {
                                "id": "wrong",
                                "attributes": {
                                    "name": "Meddle Tribute",
                                    "artistName": "Various Artists",
                                },
                            },
                        ]
                    }
                }
            }
        ]
    )
    client = AppleMusicClient(
        http_client=http,
        developer_token="token",
        storefront="ch",
    )

    results = client.search_release(album="Meddle", artist="Pink Floyd")

    assert [result["id"] for result in results] == ["good"]
    assert results[0]["cover_art_url"] == "https://img/500x500.jpg"
    assert results[0]["barcode"] == "190295996483"
    assert "/catalog/ch/search" in http.calls[0][0]
    assert http.calls[0][1]["headers"]["Authorization"] == "Bearer token"


def test_apple_music_album_details_include_isrc_tracklist():
    http = JsonHttpStub(
        [
            {
                "data": [
                    {
                        "id": "album-id",
                        "attributes": {
                            "name": "Meddle",
                            "artistName": "Pink Floyd",
                            "releaseDate": "2016-01-01",
                            "upc": "190295996483",
                            "recordLabel": "Pink Floyd Records",
                            "genreNames": ["Rock"],
                        },
                        "relationships": {
                            "tracks": {
                                "data": [
                                    {
                                        "attributes": {
                                            "trackNumber": 1,
                                            "name": "One of These Days",
                                            "artistName": "Pink Floyd",
                                            "durationInMillis": 355000,
                                            "isrc": "GBN9Y1100001",
                                        }
                                    }
                                ]
                            }
                        },
                    }
                ]
            }
        ]
    )
    client = AppleMusicClient(http_client=http, developer_token="token")

    release = client.get_album_tracks("album-id")

    assert release is not None
    assert release.media_format == "Digital Media"
    assert release.barcode == "190295996483"
    assert release.tracks[0].duration == "5:55"
    assert release.tracks[0].isrc == "GBN9Y1100001"


def test_apple_music_without_token_is_a_noop():
    http = JsonHttpStub([])
    client = AppleMusicClient(http_client=http, developer_token="")

    assert client.search_release(album="Meddle", artist="Pink Floyd") == []
    assert http.calls == []


def test_search_service_uses_configured_apple_music_as_edition_fallback():
    apple = AppleCatalogStub()
    service = SearchService(
        musicbrainz_client=EmptyCatalogStub(),
        discogs_client=EmptyCatalogStub(),
        youtube_client_factory=lambda *_args: None,
        apple_music_client=apple,
        year_validator=YearValidatorStub(),
        deduplicator=DeduplicatorStub(),
    )

    results = service.search_releases(
        SongData(title="", artist="Pink Floyd", album="Meddle"),
        limit=5,
    )

    assert len(results) == 1
    assert results[0].source == "applemusic"
    assert results[0].barcode == "190295996483"
    assert results[0].original_release_date is None
    assert service.get_release_info("apple-id", source="applemusic") is apple.info


def test_acoustid_verifies_expected_musicbrainz_recording(monkeypatch):
    monkeypatch.setattr(
        "odysseus.clients.acoustid.shutil.which", lambda _path: "/usr/bin/fpcalc"
    )
    http = JsonHttpStub(
        [
            {
                "results": [
                    {
                        "score": 0.97,
                        "recordings": [{"id": "expected-recording"}],
                    }
                ]
            }
        ]
    )
    def runner(*args, **kwargs):
        return SimpleNamespace(
            stdout='{"duration": 355, "fingerprint": "abc123"}'
        )
    client = AcoustIDClient(
        http_client=http,
        api_key="client-key",
        fpcalc_path="fpcalc",
        runner=runner,
    )

    verification = client.verify(Path("track.mp3"), "expected-recording")

    assert verification.status == "verified"
    assert verification.score == 0.97
    assert http.calls[0][1]["params"]["meta"] == "recordingids"


def test_acoustid_reports_high_confidence_mismatch(monkeypatch):
    monkeypatch.setattr(
        "odysseus.clients.acoustid.shutil.which", lambda _path: "/usr/bin/fpcalc"
    )
    http = JsonHttpStub(
        [{"results": [{"score": 0.94, "recordings": [{"id": "other"}]}]}]
    )
    client = AcoustIDClient(
        http_client=http,
        api_key="client-key",
        runner=lambda *args, **kwargs: SimpleNamespace(
            stdout='{"duration": 180, "fingerprint": "fingerprint"}'
        ),
    )

    verification = client.verify(Path("track.mp3"), "expected")

    assert verification.status == "mismatch"
    assert verification.recording_mbid == "other"
