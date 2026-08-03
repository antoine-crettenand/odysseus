import os
from pathlib import Path

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from odysseus.application.recording_workflow import RecordingDownloadResult
from odysseus.application.release_workflow import ReleaseDownloadResult
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong, YouTubeVideo
from odysseus.ui.gui.app import build_engine
from odysseus.ui.gui.controller import OdysseusController


class InlineThreadPool:
    def start(self, worker):
        worker.run()


class ManualThreadPool:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)

    def run_next(self):
        self.workers.pop(0).run()


class WorkflowStub:
    downloads_dir = Path("/tmp")

    def __init__(self):
        self.recording = MusicBrainzSong(
            title="Teardrop",
            artist="Massive Attack",
            album="Mezzanine",
            release_date="1998",
        )
        self.video = YouTubeVideo(
            title="Massive Attack - Teardrop",
            artist="Massive Attack",
            video_id="video-id",
            channel="Massive Attack",
        )
        self.download_calls = []
        self.cancelled = False

    def search_recordings(self, title, artist, album, year):
        return [self.recording]

    def search_videos(self, recording):
        return [self.video]

    def download(self, recording, video, quality, progress_callback):
        self.download_calls.append((recording, video, quality))
        progress_callback({"percent": 42, "speed": "2 MiB/s", "eta": 3})
        return RecordingDownloadResult(
            Path("/tmp/Teardrop.mp3"),
            metadata_applied=True,
        )

    def cancel(self):
        self.cancelled = True


class ReleaseWorkflowStub:
    def __init__(self):
        self.release = MusicBrainzSong(
            title="",
            artist="Massive Attack",
            album="Mezzanine",
            release_date="1998",
            release_type="Album",
            mbid="release-id",
        )
        self.info = ReleaseInfo(
            title="Mezzanine",
            artist="Massive Attack",
            tracks=[
                Track(1, "Angel", "Massive Attack", "6:19"),
                Track(2, "Risingson", "Massive Attack", "4:48"),
            ],
        )
        self.download_calls = []
        self.search_calls = []

    def search_releases(
        self, album, artist, year, release_type, year_from=None, year_to=None
    ):
        self.search_calls.append(("release", year, year_from, year_to))
        return [self.release]

    def search_discography(
        self,
        artist,
        year,
        release_type,
        include_compilations,
        year_from=None,
        year_to=None,
    ):
        self.search_calls.append(("discography", year, year_from, year_to))
        return [self.release]

    def get_release_info(self, release):
        return self.info

    def download(self, info, numbers, quality, jobs, progress_callback=None):
        self.download_calls.append((info, numbers, quality, jobs))
        if progress_callback:
            progress_callback(
                {
                    "stage": "splitting",
                    "status": "Splitting tracks",
                    "message": "Splitting track 1 of 2…",
                    "percent": 50,
                }
            )
        return ReleaseDownloadResult(2, 0, [])

    def cancel(self):
        pass


class ApiSettingsStub:
    def __init__(self):
        self.saved = []
        self.cleared = []

    def summary(self):
        return {
            "youtubeConfigured": True,
            "discogsConfigured": False,
            "spotifyConfigured": False,
            "appleMusicConfigured": False,
            "acoustidConfigured": False,
            "storefront": "ch",
            "storageLabel": "System keychain",
            "persistentStorage": True,
        }

    def save(self, values):
        self.saved.append(values)

    def clear_provider(self, provider):
        self.cleared.append(provider)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_desktop_controller_runs_recording_vertical_slice(qt_app):
    workflow = WorkflowStub()
    controller = OdysseusController(workflow, thread_pool=InlineThreadPool())

    controller.searchRecordings("Teardrop", "Massive Attack", "Mezzanine", "1998")
    assert controller.recordingResults[0]["album"] == "Mezzanine"

    controller.selectRecording(0)
    assert controller.videoResults[0]["channel"] == "Massive Attack"

    controller.selectVideo(0)
    assert controller.canDownload is True
    controller.downloadSelected("audio")

    assert workflow.download_calls[0][2] == "audio"
    assert controller.downloadProgress == 100
    assert controller.hasLastDownload is True
    assert "successfully" in controller.statusText


def test_desktop_qml_loads(qt_app):
    controller = OdysseusController(
        WorkflowStub(),
        thread_pool=InlineThreadPool(),
    )
    engine = build_engine(controller)

    assert len(engine.rootObjects()) == 1
    window = engine.rootObjects()[0]
    assert window.width() == 1400
    assert window.height() == 900
    assert window.minimumWidth() == 1040
    assert window.minimumHeight() == 700
    assert window.findChild(QObject, "settingsDrawer") is not None
    assert window.findChild(QObject, "discographyFilterField") is not None

    recording_search_fields = window.findChild(QObject, "recordingSearchFields")
    catalog_search_fields = window.findChild(QObject, "catalogSearchFields")
    assert recording_search_fields.property("visible") is True
    window.setProperty("searchPanelExpanded", False)
    qt_app.processEvents()
    assert recording_search_fields.property("visible") is False
    window.setProperty("uiMode", "release")
    window.setProperty("searchPanelExpanded", True)
    qt_app.processEvents()
    assert catalog_search_fields.property("visible") is True
    window.close()


def test_desktop_controller_saves_and_clears_api_settings(qt_app):
    settings = ApiSettingsStub()
    controller = OdysseusController(
        WorkflowStub(),
        settings_service=settings,
        thread_pool=InlineThreadPool(),
    )

    assert controller.apiSettings["youtubeConfigured"] is True
    assert controller.apiSettings["storefront"] == "ch"
    assert controller.saveApiSettings({"youtube_api_key": "new-key"}) is True
    assert settings.saved == [{"youtube_api_key": "new-key"}]
    assert "saved" in controller.settingsMessage
    assert controller.clearApiCredentials("youtube") is True
    assert settings.cleared == ["youtube"]


def test_desktop_controller_runs_release_and_discography_flows(qt_app):
    release_workflow = ReleaseWorkflowStub()
    controller = OdysseusController(
        WorkflowStub(),
        release_workflow,
        thread_pool=InlineThreadPool(),
    )

    controller.searchAlbums("Mezzanine", "Massive Attack", "1998", "Album")
    assert controller.catalogResults[0]["title"] == "Mezzanine"
    controller.selectCatalogRelease(0)
    assert len(controller.releaseTracks) == 2
    assert controller.selectedTrackCount == 2

    controller.toggleTrack(1)
    assert controller.selectedTrackCount == 1
    controller.downloadSelectedRelease("audio", 2)
    assert release_workflow.download_calls[0][1] == [1]
    assert controller.queueRows[0]["progress"] == 100
    assert "successfully" in controller.statusText

    controller.searchDiscography("Massive Attack", "", "Album", False)
    assert controller.catalogResults[0]["type"] == "Album"

    controller.searchDiscography(
        "Massive Attack", "", "Album", False, "1990", "2000"
    )
    assert release_workflow.search_calls[-1] == (
        "discography",
        None,
        1990,
        2000,
    )

    calls_before = len(release_workflow.search_calls)
    controller.searchAlbums(
        "Mezzanine", "Massive Attack", "1998", "Album", "1990", "2000"
    )
    assert len(release_workflow.search_calls) == calls_before
    assert "cannot be combined" in controller.statusText


def test_release_card_data_separates_original_and_edition_years(qt_app):
    controller = OdysseusController(
        WorkflowStub(),
        ReleaseWorkflowStub(),
        thread_pool=InlineThreadPool(),
    )
    controller._catalog_found(
        [
            MusicBrainzSong(
                title="",
                artist="Artist",
                album="Album",
                release_date="2021-06-01",
                original_release_date="1971-03-19",
                release_type="Album",
                release_status="Official",
                country="GB",
                label="Harvest",
                catalog_number="SHVL 795",
                barcode="077774603425",
                media_format='12" Vinyl',
                track_count=6,
                mbid="release-id",
                source="musicbrainz",
            )
        ]
    )

    card = controller.catalogResults[0]
    assert card["year"] == "1971"
    assert card["yearKind"] == "Original"
    assert card["editionYear"] == "2021"
    assert card["isReissue"] is True
    assert card["date"] == "1971-03-19 · edition 2021-06-01"
    assert card["coverArtUrl"].endswith("/release/release-id/front-250")
    assert card["source"] == "MusicBrainz"
    assert card["editionDetail"] == 'GB · 12" Vinyl · Harvest · SHVL 795 · 6 tracks'
    assert card["identifierDetail"] == "UPC/EAN 077774603425 · Official"


def test_catalog_results_are_sorted_by_displayed_release_year(qt_app):
    controller = OdysseusController(
        WorkflowStub(),
        ReleaseWorkflowStub(),
        thread_pool=InlineThreadPool(),
    )
    releases = [
        MusicBrainzSong(
            title="",
            artist="Artist",
            album="Undated",
            release_date=None,
            mbid="undated",
        ),
        MusicBrainzSong(
            title="",
            artist="Artist",
            album="Reissue",
            release_date="2021-06-01",
            original_release_date="1971-03-19",
            mbid="reissue",
        ),
        MusicBrainzSong(
            title="",
            artist="Artist",
            album="Later",
            release_date="1998",
            mbid="later",
        ),
        MusicBrainzSong(
            title="",
            artist="Artist",
            album="Earlier",
            release_date="1969",
            mbid="earlier",
        ),
    ]

    controller._catalog_found(releases)

    assert [row["title"] for row in controller.catalogResults] == [
        "Earlier",
        "Reissue",
        "Later",
        "Undated",
    ]
    assert [row["year"] for row in controller.catalogResults] == [
        "1969",
        "1971",
        "1998",
        "—",
    ]
    assert [release.mbid for release in controller._catalog_releases] == [
        "earlier",
        "reissue",
        "later",
        "undated",
    ]


def test_discography_filter_matches_metadata_and_keeps_indexes_aligned(qt_app):
    controller = OdysseusController(
        WorkflowStub(),
        ReleaseWorkflowStub(),
        thread_pool=InlineThreadPool(),
    )
    releases = [
        MusicBrainzSong(
            title="",
            artist="Massive Attack",
            album=f"Release {index}",
            release_date=str(1990 + index),
            release_type="Live" if index == 7 else "Album",
            label="Island" if index % 2 else "Virgin",
            mbid=f"release-{index}",
            source="musicbrainz",
        )
        for index in range(12)
    ]
    releases[7].album = "Special Concert"
    controller._catalog_found(releases)

    assert controller.catalogTotalCount == 12
    controller.selectCatalogRelease(0)
    assert controller.selectedCatalogIndex == 0
    assert controller.releaseTracks

    controller.filterCatalogResults("special 1997 live island")

    assert controller.catalogTotalCount == 12
    assert [row["title"] for row in controller.catalogResults] == [
        "Special Concert"
    ]
    assert controller._catalog_releases[0].mbid == "release-7"
    assert controller.selectedCatalogIndex == -1
    assert controller.releaseTracks == []

    controller.filterCatalogResults("")
    assert len(controller.catalogResults) == 12
    assert controller._catalog_releases[7].mbid == "release-7"


def test_download_queue_does_not_block_browsing(qt_app):
    workflow = WorkflowStub()
    controller = OdysseusController(workflow, thread_pool=InlineThreadPool())
    controller.searchRecordings("Teardrop", "Massive Attack", "", "")
    controller.selectRecording(0)
    controller.selectVideo(0)

    manual_pool = ManualThreadPool()
    controller.thread_pool = manual_pool
    controller.downloadSelected("audio")
    controller.downloadSelected("audio")

    assert controller.queueCount == 2
    assert controller.downloading is True
    assert controller.busy is False
    assert len(manual_pool.workers) == 1

    # Searching remains available while the first download worker is held.
    controller.thread_pool = InlineThreadPool()
    controller.searchRecordings("Angel", "Massive Attack", "", "")
    assert controller.recordingResults
    assert controller.downloading is True

    controller.thread_pool = manual_pool
    manual_pool.run_next()
    qt_app.processEvents()
    assert len(manual_pool.workers) == 1
    manual_pool.run_next()
    qt_app.processEvents()

    assert controller.queueCount == 0
    assert [row["status"] for row in controller.queueRows] == [
        "Completed",
        "Completed",
    ]


def test_download_queue_retains_visible_error(qt_app):
    workflow = WorkflowStub()

    def fail_download(*args, **kwargs):
        raise RuntimeError("yt-dlp authentication failed")

    workflow.download = fail_download
    controller = OdysseusController(workflow, thread_pool=InlineThreadPool())
    controller.searchRecordings("Teardrop", "Massive Attack", "", "")
    controller.selectRecording(0)
    controller.selectVideo(0)

    controller.downloadSelected("audio")

    assert controller.queueRows[0]["status"] == "Failed"
    assert "authentication failed" in controller.queueRows[0]["detail"]
    assert "Download failed" in controller.statusText


def test_release_queue_shows_live_cli_stage(qt_app):
    release_workflow = ReleaseWorkflowStub()
    controller = OdysseusController(
        WorkflowStub(),
        release_workflow,
        thread_pool=InlineThreadPool(),
    )
    controller.searchAlbums("Mezzanine", "Massive Attack", "", "Album")
    controller.selectCatalogRelease(0)

    manual_pool = ManualThreadPool()
    controller.thread_pool = manual_pool
    controller.downloadSelectedRelease("audio", 1)
    job = controller._current_download_job
    controller._queued_download_progressed(
        job,
        {
            "stage": "splitting",
            "status": "Splitting tracks",
            "message": "Splitting track 1 of 2…",
            "percent": 50,
        },
    )

    assert controller.queueRows[0]["stage"] == "Splitting tracks"
    assert controller.queueRows[0]["progress"] == 50
    assert controller.queueRows[0]["detail"] == "Splitting track 1 of 2…"
