from pathlib import Path

import pytest

from odysseus.application.release_workflow import ReleaseWorkflow
from odysseus.clients.acoustid import AudioVerification
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong


class SearchStub:
    def __init__(self):
        self.release_calls = []
        self.discography_calls = []
        self.info_calls = []
        self.results = []
        self.info = None

    def search_releases(self, song, **kwargs):
        self.release_calls.append((song, kwargs))
        return self.results

    def search_artist_releases(self, artist, **kwargs):
        self.discography_calls.append((artist, kwargs))
        return self.results

    def get_release_info(self, mbid, source):
        self.info_calls.append((mbid, source))
        return self.info


class DownloadStub:
    def __init__(self):
        self.cancelled = False

    def cancel_active_downloads(self):
        self.cancelled = True


class OrchestratorStub:
    def __init__(self):
        self.calls = []
        self.last_failed_track_numbers = [2]
        self.path_manager = None

    def download_release_tracks(
        self, info, numbers, quality, silent, jobs, progress_callback=None
    ):
        self.calls.append((info, numbers, quality, silent, jobs))
        if progress_callback:
            progress_callback(
                {
                    "stage": "splitting",
                    "status": "Splitting tracks",
                    "message": "Splitting track 1 of 2…",
                    "percent": 50,
                }
            )
        return 1, 1


class PathManagerStub:
    def __init__(self, paths):
        self.paths = paths

    def get_existing_tracks(self, info, numbers):
        return {number: self.paths[number] for number in numbers if number in self.paths}


class AcoustIDStub:
    def __init__(self, results):
        self.results = list(results)

    def is_available(self):
        return True

    def verify(self, path, mbid):
        return self.results.pop(0)


def make_release():
    return MusicBrainzSong(
        title="",
        artist="Massive Attack",
        album="Mezzanine",
        release_date="1998",
        release_type="Album",
        mbid="release-id",
    )


def make_info():
    return ReleaseInfo(
        title="Mezzanine",
        artist="Massive Attack",
        tracks=[
            Track(1, "Angel", "Massive Attack", "6:19"),
            Track(2, "Risingson", "Massive Attack", "4:48"),
        ],
    )


def test_release_workflow_searches_album_and_discography():
    search = SearchStub()
    search.results = [make_release()]
    workflow = ReleaseWorkflow(search, DownloadStub(), OrchestratorStub())

    assert workflow.search_releases(
        "Mezzanine", "Massive Attack", year=1998, release_type="Album"
    ) == search.results
    song, kwargs = search.release_calls[0]
    assert (song.album, song.artist, song.release_year) == (
        "Mezzanine",
        "Massive Attack",
        1998,
    )
    assert kwargs["release_type"] == "Album"

    assert workflow.search_discography(
        "Massive Attack",
        year_from=1990,
        year_to=2000,
        include_compilations=True,
    ) == search.results
    assert search.discography_calls[0][1]["include_compilations"] is True
    assert search.discography_calls[0][1]["year_from"] == 1990
    assert search.discography_calls[0][1]["year_to"] == 2000

    with pytest.raises(ValueError, match="cannot be combined"):
        workflow.search_releases(
            "Mezzanine",
            "Massive Attack",
            year=1998,
            year_from=1990,
            year_to=2000,
        )


def test_release_workflow_loads_and_downloads_selected_tracks():
    search = SearchStub()
    search.info = make_info()
    orchestrator = OrchestratorStub()
    workflow = ReleaseWorkflow(search, DownloadStub(), orchestrator)

    info = workflow.get_release_info(make_release())
    result = workflow.download(info, [2, 1, 2], quality="audio", jobs=3)

    assert search.info_calls == [("release-id", "musicbrainz")]
    assert orchestrator.calls == [(info, [1, 2], "audio", True, 3)]
    assert result.processed == 1
    assert result.failed == 1
    assert result.failed_track_numbers == [2]


def test_release_workflow_forwards_structured_progress():
    orchestrator = OrchestratorStub()
    workflow = ReleaseWorkflow(SearchStub(), DownloadStub(), orchestrator)
    events = []

    workflow.download(make_info(), [1], progress_callback=events.append)

    assert events == [
        {
            "stage": "splitting",
            "status": "Splitting tracks",
            "message": "Splitting track 1 of 2…",
            "percent": 50,
        }
    ]


def test_release_workflow_summarizes_track_fingerprint_checks(tmp_path):
    info = ReleaseInfo(
        title="Mezzanine",
        artist="Massive Attack",
        tracks=[
            Track(1, "Angel", "Massive Attack", "6:19", "recording-1"),
            Track(2, "Risingson", "Massive Attack", "4:48", "recording-2"),
        ],
    )
    orchestrator = OrchestratorStub()
    orchestrator.path_manager = PathManagerStub(
        {1: tmp_path / "01 - Angel.mp3", 2: tmp_path / "02 - Risingson.mp3"}
    )
    acoustid = AcoustIDStub(
        [
            AudioVerification("verified", 0.99, "recording-1"),
            AudioVerification("inconclusive", 0.45, "other"),
        ]
    )
    workflow = ReleaseWorkflow(
        SearchStub(), DownloadStub(), orchestrator, acoustid_client=acoustid
    )

    result = workflow.download(info, [1, 2])

    assert result.verified == 1
    assert result.verification_mismatches == 0
    assert result.verification_inconclusive == 1


def test_release_workflow_validates_tracks_and_cancels():
    download = DownloadStub()
    workflow = ReleaseWorkflow(SearchStub(), download, OrchestratorStub())

    with pytest.raises(ValueError, match="at least one"):
        workflow.download(make_info(), [])
    with pytest.raises(ValueError, match="invalid track"):
        workflow.download(make_info(), [3])

    workflow.cancel()
    assert download.cancelled is True
