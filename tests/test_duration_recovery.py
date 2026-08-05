"""Tests for DurationRecoveryService."""

from unittest.mock import MagicMock

from odysseus.domain.music.metadata.duration_recovery import DurationRecoveryService
from odysseus.models.releases import ReleaseInfo, Track
from odysseus.models.search_results import MusicBrainzSong

def test_duration_recovery_skips_unrelated_first_recording():
    wrong = MusicBrainzSong(
        title="Different Song",
        artist="Artist",
        album="Album",
        mbid="wrong",
        score=100,
    )
    right = MusicBrainzSong(
        title="Target",
        artist="Artist",
        album="Album",
        mbid="right",
        score=1,
    )
    musicbrainz = MagicMock(base_url="https://musicbrainz.test")
    musicbrainz.search_recording.return_value = [wrong, right]
    musicbrainz._make_request.side_effect = (
        lambda url, _params: {
            "length": 600000 if url.endswith("wrong") else 180000
        }
    )
    spotify = MagicMock(access_token=None)
    recovery = DurationRecoveryService(musicbrainz, spotify, MagicMock())

    duration = recovery.recover_track_duration(
        Track(position=1, title="Target", artist="Artist"),
        ReleaseInfo(title="Album", artist="Artist"),
    )

    assert duration == "3:00"
    assert "right" in musicbrainz._make_request.call_args.args[0]
