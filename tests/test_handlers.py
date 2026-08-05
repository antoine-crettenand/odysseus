"""Tests for UI handlers."""

from unittest.mock import MagicMock

from odysseus.models.search_results import YouTubeVideo
from odysseus.ui.handlers.metadata_handler import MetadataHandler
from odysseus.ui.handlers.recording_handler import RecordingHandler

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
    handler.recording_workflow = MagicMock()
    handler.recording_workflow.download.return_value = MagicMock(
        path="/tmp/track.flac",
        warning=None,
        verification_status="not_run",
    )

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
    handler.recording_workflow.download.assert_called_once_with(
        selected_song, selected_video, quality="audio"
    )

def test_metadata_handler_uses_plural_release_search(tmp_path):
    audio_file = tmp_path / "track.mp3"
    audio_file.touch()
    handler = MetadataHandler.__new__(MetadataHandler)
    handler.search_service = MagicMock()
    handler.search_service.search_releases.return_value = []
    handler.display_manager = MagicMock()
    handler.display_manager.show_loading_spinner.side_effect = (
        lambda _message, function, *args, **kwargs: function(*args, **kwargs)
    )

    outcome = handler.handle(
        str(audio_file),
        artist="Artist",
        album="Album",
    )

    assert outcome.succeeded is False
    handler.search_service.search_releases.assert_called_once()
    handler.search_service.search_release.assert_not_called()
