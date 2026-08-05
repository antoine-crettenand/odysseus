"""Regression tests for defects fixed after the refactor review."""

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from odysseus.clients.file_splitter import FileSplitter
from odysseus.core.http.network_agent import NetworkAgent
from odysseus.core.http import HttpClient
from odysseus.core.retry import SubprocessRetryStrategy
from odysseus.domain.media.cover_art.fetcher import CoverArtFetcher
from odysseus.domain.music.download.strategies.full_album import (
    ChapterAligner,
    FullAlbumDownloadPipeline,
)
from odysseus.domain.music.search.deduplicator import ResultDeduplicator
from odysseus.domain.music.validation.title_matcher import TitleMatcher
from odysseus.domain.music.validation.video_validator import VideoValidator
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong


def _aligner():
    return ChapterAligner(
        video_validator=VideoValidator(MagicMock()),
        title_matcher=TitleMatcher(),
    )


def _tracks(count: int, duration: str = "03:00"):
    return [
        Track(position=index, title=f"Track {index}", artist="Artist", duration=duration)
        for index in range(1, count + 1)
    ]


def test_file_splitter_keeps_failed_slots_index_aligned(tmp_path):
    video = tmp_path / "album.mp3"
    video.write_bytes(b"fake")
    tracks = _tracks(3)
    timestamps = [
        {"start_time": 0, "end_time": 60, "track": tracks[0]},
        {"start_time": 60, "end_time": 120, "track": tracks[1]},
        {"start_time": 120, "end_time": 180, "track": tracks[2]},
    ]
    metadata = [
        {"title": track.title, "track_number": track.position}
        for track in tracks
    ]

    def fake_run(cmd, **kwargs):
        output = Path(cmd[-1])
        # Fail only the middle track.
        if "02 - Track 2.mp3" in output.name:
            raise subprocess.CalledProcessError(1, cmd, stderr="ffmpeg failed")
        output.write_bytes(b"ok")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("odysseus.clients.file_splitter.subprocess.run", side_effect=fake_run):
        results = FileSplitter.split_video_into_tracks(
            video,
            timestamps,
            tmp_path,
            metadata,
        )

    assert len(results) == 3
    assert results[0] is not None and results[0].name.startswith("01 -")
    assert results[1] is None
    assert results[2] is not None and results[2].name.startswith("03 -")


def test_metadata_application_skips_failed_split_slots():
    pipeline = FullAlbumDownloadPipeline.__new__(FullAlbumDownloadPipeline)
    pipeline.presenter = MagicMock()
    pipeline.presenter.create_download_progress_bar.return_value = (
        MagicMock(),
        "task",
    )
    pipeline.metadata_service = MagicMock()
    pipeline.path_manager = MagicMock()
    tracks = _tracks(3)
    timestamps = [{"track": track} for track in tracks]
    split_files = [
        Path("/tmp/01.mp3"),
        None,
        Path("/tmp/03.mp3"),
    ]

    downloaded, failed = pipeline._apply_metadata_to_split_files(
        split_files,
        timestamps,
        ReleaseInfo(title="Album", artist="Artist", tracks=tracks),
        cover_art_data=None,
        existing_files_before_split=set(),
        youtube_url="https://youtube.test/v",
        silent=True,
    )

    assert downloaded == 2
    assert failed == 1
    applied_paths = [
        call.args[0]
        for call in pipeline.metadata_service.apply_metadata_with_cover_art.call_args_list
    ]
    assert applied_paths == [Path("/tmp/01.mp3"), Path("/tmp/03.mp3")]


def test_chapter_alignment_scales_for_large_albums_with_extras():
    aligner = _aligner()
    tracks = _tracks(40)
    chapters = [{"start_time": 0, "end_time": 10, "title": "Intro"}]
    start = 10.0
    for track in tracks:
        chapters.append({
            "start_time": start,
            "end_time": start + 180,
            "title": track.title,
        })
        start += 180

    timestamps = aligner._align_chapters_to_tracks(
        chapters,
        tracks,
        tracks,
        silent=True,
    )

    assert len(timestamps) == 40
    assert timestamps[0]["chapter_title"] == "Track 1"
    assert timestamps[0]["start_time"] == 10


def test_unavailable_video_errors_are_not_retryable():
    retryable, reason = SubprocessRetryStrategy.is_retryable_error(
        "ERROR: [youtube] abc: Video unavailable"
    )
    assert retryable is False
    assert reason == "Unavailable"

    retryable, reason = SubprocessRetryStrategy.is_retryable_error(
        "Private video. Sign in if you've been granted access"
    )
    assert retryable is False
    assert reason == "Unavailable"


def test_cancel_stops_subprocess_retries():
    strategy = SubprocessRetryStrategy(max_retries=3, base_delay=10)
    failure = subprocess.CalledProcessError(1, ["yt-dlp"], stderr="connection reset")

    def fail_then_cancel(cmd, progress_callback=None):
        strategy.cancel_active()
        raise failure

    with patch.object(strategy, "_run_attempt", side_effect=fail_then_cancel):
        with pytest.raises(subprocess.CalledProcessError):
            strategy.execute_with_progress(["yt-dlp"], quiet=True)

    assert strategy.is_cancelled()


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


def test_cover_art_rejects_non_image_http_200():
    fetcher = CoverArtFetcher(http_client=MagicMock(), cache_manager=None)
    response = MagicMock()
    response.status_code = 200
    response.content = b"<html>cdn error</html>"
    fetcher.http_client.get.return_value = response

    result = fetcher.fetch_cover_art_from_url("https://cdn.test/cover.jpg")

    assert result is None
    assert not fetcher.cover_art_cache.has("https://cdn.test/cover.jpg")


def test_cover_art_accepts_jpeg_magic_bytes():
    assert CoverArtFetcher._is_image_payload(b"\xff\xd8\xff" + b"\x00" * 20)
    assert CoverArtFetcher._is_image_payload(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    )
    assert not CoverArtFetcher._is_image_payload(b"{'error': true}")


def test_accepted_403_counts_toward_circuit_breaker():
    response = MagicMock(spec=requests.Response)
    response.status_code = 403
    response.headers = {}
    session = MagicMock()
    session.get.return_value = response
    session_manager = MagicMock()
    session_manager.get_session.return_value = session
    client = HttpClient(
        session_manager=session_manager,
        default_request_delay=0,
        circuit_breaker_threshold=2,
        circuit_breaker_cooldown=30,
    )

    first = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )
    second = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )
    third = client.get(
        "https://example.test",
        max_retries=0,
        accepted_status_codes=(403,),
        session_name="discogs",
    )

    assert first is response
    assert second is response
    assert third is None
    assert client.get_provider_health("discogs")["cooldown_remaining"] > 0


def test_session_request_delay_override_is_honored():
    client = HttpClient(default_request_delay=1.0)
    client.set_session_request_delay("spotify", 0.1)
    client._last_request_times["spotify"] = 0.0

    with patch("odysseus.core.http.http_client.time.monotonic", return_value=0.05), patch(
        "odysseus.core.http.http_client.time.sleep"
    ) as sleep:
        client._apply_request_delay("spotify")

    sleep.assert_called_once()
    assert sleep.call_args.args[0] == pytest.approx(0.05)


def test_network_agent_strategy_switch_is_thread_safe():
    agent = NetworkAgent("TestAgent/1.0")

    def switch_many():
        for _ in range(50):
            agent.switch_to_next_strategy(RuntimeError("boom"))

    threads = [threading.Thread(target=switch_many) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert 0 <= agent.current_strategy_index < len(agent.strategies)
    # Locking preserves one history entry per switch with no lost updates.
    assert len(agent.error_history) == 200
