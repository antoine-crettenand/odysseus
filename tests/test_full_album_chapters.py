"""Regression tests for full-album chapter alignment."""

from unittest.mock import MagicMock, patch

from odysseus.clients.file_splitter import FileSplitter
from odysseus.clients.youtube_downloader import YouTubeDownloader
from odysseus.domain.music.download.strategies.full_album import ChapterAligner
from odysseus.domain.music.validation.title_matcher import TitleMatcher
from odysseus.domain.music.validation.video_validator import VideoValidator
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.utils.pattern_matcher import PatternMatcher


def _aligner():
    return ChapterAligner(
        video_validator=VideoValidator(MagicMock()),
        title_matcher=TitleMatcher(),
    )


def _black_focus_release():
    titles_and_durations = [
        ("Black Focus", "04:34"),
        ("Strings of Light", "08:29"),
        ("Remembrance", "09:01"),
        ("Yo Chavez", "03:59"),
        ("Ayla", "00:46"),
        ("O.G.", "00:47"),
        ("Lowrider", "04:28"),
        ("Mansur’s Message", "02:06"),
        ("WingTai Drums", "01:17"),
        ("Joint 17", "08:19"),
    ]
    tracks = [
        Track(
            position=index,
            title=title,
            artist="Yussef Kamaal",
            duration=duration,
        )
        for index, (title, duration) in enumerate(titles_and_durations, start=1)
    ]
    return ReleaseInfo(
        title="Black Focus",
        artist="Yussef Kamaal",
        release_date="2016-11-04",
        tracks=tracks,
    )


def _chapters_with_intro(release):
    chapters = [
        {
            "start_time": 0,
            "end_time": 15,
            "title": "Intro",
        }
    ]
    start = 15.0
    validator = VideoValidator(MagicMock())
    for track in release.tracks:
        duration = validator._parse_duration_to_seconds(track.duration)
        chapters.append({
            "start_time": start,
            "end_time": start + duration,
            "title": track.title,
        })
        start += duration
    return chapters


def test_extra_intro_chapter_is_skipped_instead_of_becoming_track_one():
    aligner = _aligner()
    release = _black_focus_release()
    chapters = _chapters_with_intro(release)

    timestamps = aligner._align_chapters_to_tracks(
        chapters,
        release.tracks,
        release.tracks,
        silent=True,
    )

    assert len(timestamps) == 10
    assert timestamps[0]["track"].title == "Black Focus"
    assert timestamps[0]["chapter_title"] == "Black Focus"
    assert timestamps[0]["start_time"] == 15
    assert timestamps[0]["end_time"] == 15 + 274


def test_implausibly_short_aligned_chapter_rejects_video():
    aligner = _aligner()
    release = _black_focus_release()
    chapters = _chapters_with_intro(release)[1:]
    chapters[0]["end_time"] = chapters[0]["start_time"] + 15

    timestamps = aligner._align_chapters_to_tracks(
        chapters,
        release.tracks,
        release.tracks,
        silent=True,
    )

    assert timestamps == []


def test_duration_fallback_keeps_full_album_offset_for_partial_selection():
    aligner = _aligner()
    tracks = [
        Track(index, f"Track {index}", "Artist", "01:00")
        for index in range(1, 5)
    ]

    timestamps = aligner._calculate_track_timestamps_from_durations(
        tracks,
        [3],
    )

    assert len(timestamps) == 1
    assert timestamps[0]["track"].position == 3
    assert timestamps[0]["start_time"] == 120
    assert timestamps[0]["end_time"] == 180


def test_youtube_chapter_extraction_preserves_end_time():
    downloader = YouTubeDownloader.__new__(YouTubeDownloader)
    downloader.get_video_info = MagicMock(return_value={
        "chapters": [{
            "start_time": 10,
            "end_time": 20,
            "title": "Track",
        }]
    })

    chapters = downloader.get_video_chapters("https://youtube.test/video")

    assert chapters == [{
        "start_time": 10,
        "end_time": 20,
        "title": "Track",
    }]


def test_vinyl_and_listening_uploads_are_rejected():
    validator = VideoValidator(MagicMock())

    assert validator.is_vinyl_or_listening_upload(
        "Artist - Album [FULL ALBUM] VINYL"
    )
    assert validator.is_vinyl_or_listening_upload(
        "Artist - Album [FULL ALBUM]",
        {"description": "A needle drop from the original LP"},
    )
    assert PatternMatcher.is_live_or_non_album_video(
        "Artist - Album full album vinyl rip"
    )


def test_vinyl_marker_hidden_in_chapters_rejects_video():
    aligner = _aligner()
    release = _black_focus_release()
    chapters = _chapters_with_intro(release)
    chapters[0]["title"] = "Needle drop intro"

    assert aligner._align_chapters_to_tracks(
        chapters,
        release.tracks,
        release.tracks,
        silent=True,
    ) == []


def test_chapter_alignment_uses_dp_instead_of_combinatorial_blowup():
    aligner = _aligner()
    tracks = [
        Track(index, f"Track {index}", "Artist", "02:00")
        for index in range(1, 51)
    ]
    chapters = [{"start_time": 0, "end_time": 5, "title": "Silence"}]
    start = 5.0
    for track in tracks:
        chapters.append({
            "start_time": start,
            "end_time": start + 120,
            "title": track.title,
        })
        start += 120
    chapters.append({
        "start_time": start,
        "end_time": start + 20,
        "title": "Outro",
    })

    timestamps = aligner._align_chapters_to_tracks(
        chapters,
        tracks,
        tracks[:3],
        silent=True,
    )

    assert len(timestamps) == 3
    assert timestamps[0]["track"].position == 1
    assert timestamps[0]["chapter_title"] == "Track 1"


def test_bad_existing_split_is_marked_for_replacement(temp_dir):
    existing_file = temp_dir / "01 - Black Focus.mp3"
    existing_file.touch()
    timestamp = {
        "start_time": 15,
        "end_time": 289,
        "track": Track(1, "Black Focus", "Yussef Kamaal", "04:34"),
    }

    with patch(
        "odysseus.clients.file_splitter.get_file_duration",
        return_value=15,
    ):
        assert not FileSplitter._is_existing_split_valid(
            existing_file,
            timestamp,
        )

    with patch(
        "odysseus.clients.file_splitter.get_file_duration",
        return_value=274,
    ):
        assert FileSplitter._is_existing_split_valid(
            existing_file,
            timestamp,
        )

def _tracks(count: int, duration: str = "03:00"):
    return [
        Track(position=index, title=f"Track {index}", artist="Artist", duration=duration)
        for index in range(1, count + 1)
    ]

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

def test_duration_fallback_rejects_unknown_preceding_offset():
    aligner = ChapterAligner.__new__(ChapterAligner)
    aligner.video_validator = MagicMock()
    aligner.video_validator._parse_duration_to_seconds.side_effect = (
        lambda value: None if value is None else 180
    )
    tracks = [
        Track(1, "Unknown", "Artist", None),
        Track(2, "Selected", "Artist", "03:00"),
    ]

    timestamps = aligner._calculate_track_timestamps_from_durations(
        tracks,
        [2],
    )

    assert timestamps == []

def test_duration_fallback_ignores_missing_durations_after_selection():
    aligner = ChapterAligner.__new__(ChapterAligner)
    aligner.video_validator = MagicMock()
    aligner.video_validator._parse_duration_to_seconds.side_effect = (
        lambda value: None if value is None else 60
    )
    tracks = [
        Track(1, "Selected", "Artist", "01:00"),
        Track(2, "Later", "Artist", None),
    ]

    timestamps = aligner._calculate_track_timestamps_from_durations(
        tracks,
        [1],
    )

    assert timestamps[0]["start_time"] == 0
    assert timestamps[0]["end_time"] == 60
