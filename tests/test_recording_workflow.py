from pathlib import Path

import pytest

from odysseus.application.recording_workflow import RecordingWorkflow
from odysseus.clients.acoustid import AudioVerification
from odysseus.models.search_results import MusicBrainzSong, YouTubeVideo


class SearchServiceStub:
    def __init__(self):
        self.recording_calls = []
        self.youtube_calls = []
        self.recordings = []
        self.videos = []

    def search_recordings(self, song, offset=0, limit=None):
        self.recording_calls.append((song, offset, limit))
        return self.recordings

    def search_youtube(self, query, max_results=3, offset=0):
        self.youtube_calls.append((query, max_results, offset))
        return self.videos


class DownloadServiceStub:
    def __init__(self, result):
        self.downloads_dir = Path("/tmp/odysseus-downloads")
        self.result = result
        self.audio_calls = []
        self.video_calls = []
        self.cancelled = False

    def download_high_quality_audio(self, url, **kwargs):
        self.audio_calls.append((url, kwargs))
        return self.result

    def download_video(self, url, **kwargs):
        self.video_calls.append((url, kwargs))
        return self.result

    def cancel_active_downloads(self):
        self.cancelled = True


class MetadataServiceStub:
    def __init__(self, applied=True, apply_error=None, cover_error=None):
        self.applied = applied
        self.apply_error = apply_error
        self.cover_error = cover_error
        self.cover_calls = []
        self.final_metadata = None
        self.file_calls = []

    def fetch_cover_art(self, mbid, console=None):
        self.cover_calls.append((mbid, console))
        if self.cover_error:
            raise self.cover_error
        return b"cover"

    def set_final_metadata(self, metadata):
        self.final_metadata = metadata

    def apply_metadata_to_file(self, path, quiet=False):
        self.file_calls.append((path, quiet))
        if self.apply_error:
            raise self.apply_error
        return self.applied


class AcoustIDStub:
    def __init__(self, status="verified"):
        self.status = status
        self.calls = []

    def is_available(self):
        return True

    def verify(self, path, expected_mbid):
        self.calls.append((path, expected_mbid))
        return AudioVerification(self.status, 0.96, "fingerprinted-recording")


def make_recording():
    return MusicBrainzSong(
        title="Teardrop",
        artist="Massive Attack",
        album="Mezzanine",
        release_date="1998-04-20",
        genre="Trip hop",
        mbid="recording-id",
        score=100,
    )


def make_video():
    return YouTubeVideo(
        title="Massive Attack - Teardrop",
        artist="Massive Attack",
        video_id="video-id",
        channel="Massive Attack",
    )


def test_recording_workflow_searches_metadata_and_videos():
    search = SearchServiceStub()
    recording = make_recording()
    video = make_video()
    search.recordings = [recording]
    search.videos = [video]
    workflow = RecordingWorkflow(
        search,
        DownloadServiceStub((Path("track.mp3"), False)),
        MetadataServiceStub(),
    )

    assert workflow.search_recordings(
        "Teardrop", "Massive Attack", "Mezzanine", 1998, offset=-2, limit=0
    ) == [recording]
    song, offset, limit = search.recording_calls[0]
    assert (song.title, song.artist, song.album, song.release_year) == (
        "Teardrop",
        "Massive Attack",
        "Mezzanine",
        1998,
    )
    assert (offset, limit) == (0, 1)

    assert workflow.search_videos(recording, offset=-1, limit=0) == [video]
    assert search.youtube_calls == [("Massive Attack Teardrop", 1, 0)]


def test_recording_workflow_downloads_audio_and_applies_metadata(tmp_path):
    output = tmp_path / "Teardrop.mp3"
    download = DownloadServiceStub((output, False))
    metadata = MetadataServiceStub()
    workflow = RecordingWorkflow(SearchServiceStub(), download, metadata)
    progress_events = []
    progress_callback = progress_events.append

    result = workflow.download(
        make_recording(),
        make_video(),
        progress_callback=progress_callback,
    )

    assert result.path == output
    assert result.metadata_applied is True
    assert result.warning is None
    url, kwargs = download.audio_calls[0]
    assert url == "https://www.youtube.com/watch?v=video-id"
    assert kwargs["metadata"] == {
        "title": "Teardrop",
        "artist": "Massive Attack",
        "album": "Mezzanine",
        "year": 1998,
    }
    assert kwargs["progress_callback"] is progress_callback
    assert metadata.cover_calls == [("recording-id", None)]
    assert metadata.final_metadata.cover_art_data == b"cover"
    assert metadata.file_calls == [(str(output), True)]


def test_recording_workflow_reports_advisory_fingerprint_mismatch(tmp_path):
    output = tmp_path / "Teardrop.mp3"
    acoustid = AcoustIDStub("mismatch")
    workflow = RecordingWorkflow(
        SearchServiceStub(),
        DownloadServiceStub((output, False)),
        MetadataServiceStub(),
        acoustid_client=acoustid,
    )

    result = workflow.download(make_recording(), make_video())

    assert result.path == output
    assert result.verification_status == "mismatch"
    assert result.verification_score == 0.96
    assert "different recording" in result.warning
    assert acoustid.calls == [(output, "recording-id")]


def test_recording_workflow_preserves_download_when_tagging_fails(tmp_path):
    output = tmp_path / "Teardrop.mp3"
    workflow = RecordingWorkflow(
        SearchServiceStub(),
        DownloadServiceStub((output, False)),
        MetadataServiceStub(apply_error=RuntimeError("read-only tags")),
    )

    result = workflow.download(make_recording(), make_video())

    assert result.path == output
    assert result.metadata_applied is False
    assert "read-only tags" in result.warning


def test_recording_workflow_still_tags_when_cover_fetch_fails(tmp_path):
    output = tmp_path / "Teardrop.mp3"
    metadata = MetadataServiceStub(cover_error=RuntimeError("art unavailable"))
    workflow = RecordingWorkflow(
        SearchServiceStub(),
        DownloadServiceStub((output, False)),
        metadata,
    )

    result = workflow.download(make_recording(), make_video())

    assert result.metadata_applied is True
    assert metadata.file_calls == [(str(output), True)]
    assert "art unavailable" in result.warning


def test_recording_workflow_rejects_video_without_url_and_can_cancel(tmp_path):
    download = DownloadServiceStub((tmp_path / "unused.mp3", False))
    workflow = RecordingWorkflow(
        SearchServiceStub(),
        download,
        MetadataServiceStub(),
    )
    video = make_video()
    video.video_id = ""
    video.url_suffix = ""

    with pytest.raises(ValueError, match="no downloadable URL"):
        workflow.download(make_recording(), video)

    workflow.cancel()
    assert download.cancelled is True
