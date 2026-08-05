"""Regression tests for runtime-only import and path boundaries."""

from unittest.mock import MagicMock, patch

from odysseus.clients.file_splitter import FileSplitter
from odysseus.clients.path_utils import PathUtils
from odysseus.domain.music.download.strategies import full_album_strategy
from odysseus.domain.music.download.strategies.full_album_strategy import (
    FullAlbumStrategy,
)
from odysseus.domain.music.search.search_service import SearchService
from odysseus.domain.music.search.video_searcher import VideoSearcher
from odysseus.models.search_results import YouTubeVideo
from odysseus.ui.handlers.recording_handler import RecordingHandler


def test_safe_path_rejects_sibling_with_common_prefix(temp_dir):
    base_dir = temp_dir / "downloads"
    sibling = temp_dir / "downloads-escape" / "track.mp3"

    assert PathUtils._resolve_safe_path(sibling, base_dir) == base_dir


def test_download_path_uses_selected_metadata_not_search_query(temp_dir):
    downloads_dir = temp_dir / "downloads"
    query_path = PathUtils.get_organized_path(
        downloads_dir,
        {
            "artist": "Search Artist",
            "album": "Search Release",
            "year": 1999,
        },
    )
    selected_path = PathUtils.create_organized_path(
        downloads_dir,
        {
            "artist": "Canonical Artist",
            "album": "Canonical Release",
            "year": 2001,
        },
    )

    assert not query_path.exists()
    assert selected_path.is_dir()
    assert selected_path == (
        downloads_dir / "Canonical Artist" / "Canonical Release (2001)"
    )


def test_full_album_strategy_resolves_file_splitter_from_clients_package():
    assert full_album_strategy.FileSplitter is FileSplitter


def test_invalid_video_warning_uses_injected_console():
    search_service = MagicMock()
    video = YouTubeVideo(
        title="Wrong result",
        artist="Other artist",
        video_id="video-id",
    )
    search_service.search_youtube.return_value = [video]

    validator = MagicMock()
    validator.validate_video_for_track.return_value = (False, "title mismatch")
    validator.is_live_version.return_value = True

    title_matcher = MagicMock()
    title_matcher.are_titles_similar.return_value = False

    presenter = MagicMock()
    presenter.show_loading_spinner.side_effect = (
        lambda _message, function, *args: function(*args)
    )

    track = MagicMock(title="Expected title", artist="Expected artist")
    release = MagicMock(
        title="Expected album",
        artist="Expected artist",
        release_type="Album",
        url=None,
    )

    searcher = VideoSearcher(
        search_service,
        validator,
        title_matcher,
        presenter,
    )
    searcher.search_and_match_video(track, release)

    assert any(
        "Skipping invalid video" in str(call)
        for call in presenter.print.call_args_list
    )


def test_youtube_search_applies_offset_to_fetched_results():
    videos = [
        YouTubeVideo(
            title=f"Video {index}",
            artist="Artist",
            video_id=str(index),
        )
        for index in range(5)
    ]
    youtube_client = MagicMock(videos=videos)
    factory = MagicMock(return_value=youtube_client)
    service = SearchService.__new__(SearchService)
    service.youtube_client_factory = factory

    results = service.search_youtube("query", max_results=2, offset=3)

    factory.assert_called_once_with("query", 5)
    assert results == videos[3:5]


def test_youtube_search_treats_negative_offset_as_zero():
    video = YouTubeVideo(title="Video", artist="Artist", video_id="1")
    factory = MagicMock(return_value=MagicMock(videos=[video]))
    service = SearchService.__new__(SearchService)
    service.youtube_client_factory = factory

    results = service.search_youtube("query", max_results=2, offset=-3)

    factory.assert_called_once_with("query", 2)
    assert results == [video]


def test_provider_failure_is_isolated_from_other_searches():
    def fail():
        raise RuntimeError("provider unavailable")

    assert SearchService._safe_provider_search("Test provider", fail) == []


def test_recording_reshuffle_advances_youtube_offset():
    first_batch = [
        YouTubeVideo(title="First", artist="Artist", video_id="1"),
        YouTubeVideo(title="Second", artist="Artist", video_id="2"),
    ]
    selected_video = YouTubeVideo(
        title="Third",
        artist="Artist",
        video_id="3",
    )
    batches = iter((first_batch, [selected_video]))

    handler = RecordingHandler.__new__(RecordingHandler)
    handler.search_service = MagicMock()
    handler.search_service.search_youtube.return_value = []
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
        (("Artist Title", 3, 2),),
    ]
    handler.recording_workflow.download.assert_called_once_with(
        selected_song, selected_video, quality="audio"
    )


def test_full_album_temp_file_is_cleaned_when_split_fails(temp_dir):
    strategy = FullAlbumStrategy.__new__(FullAlbumStrategy)
    strategy.presenter = MagicMock()
    strategy.path_manager = MagicMock()
    strategy.path_manager.get_release_folder_path.return_value = temp_dir
    strategy.download_service = MagicMock()
    strategy.download_service.downloader._create_organized_path.return_value = (
        temp_dir
    )

    video = YouTubeVideo(
        title="Full album",
        artist="Artist",
        video_id="album",
    )
    track = MagicMock(position=1)
    timestamp = {"track": track, "start_time": 0, "end_time": 60}
    full_video_path = temp_dir / "full-album.webm"

    strategy._should_skip_strategy = MagicMock(return_value=False)
    strategy._prepare_cover_art = MagicMock(return_value=None)
    strategy._search_full_album_videos = MagicMock(return_value=[video])
    strategy._validate_video = MagicMock(return_value=True)
    strategy._get_selected_tracks = MagicMock(return_value=[track])
    strategy._prepare_track_timestamps = MagicMock(return_value=[timestamp])
    strategy._prepare_album_metadata = MagicMock(return_value={})
    strategy._download_full_album_video = MagicMock(
        return_value=full_video_path
    )
    strategy._prepare_metadata_list = MagicMock(return_value=[{}])
    strategy._split_video_into_tracks = MagicMock(
        side_effect=RuntimeError("split failed")
    )
    strategy._cleanup_temp_files = MagicMock()

    release = MagicMock()
    with patch.object(
        full_album_strategy.FileSplitter,
        "_get_existing_files_before_split",
        return_value=set(),
    ):
        result = strategy.download(release, [1], "audio", silent=True)

    assert result == (None, None)
    strategy._cleanup_temp_files.assert_called_once_with(full_video_path)


def test_handler_formats_plain_value_errors():
    handler = RecordingHandler.__new__(RecordingHandler)
    handler.display_manager = MagicMock()

    handler._handle_validation_error(ValueError("invalid input"))

    handler.display_manager.console.print.assert_called_once_with(
        "[bold red]✗[/bold red] invalid input"
    )
