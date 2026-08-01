"""
Duration Recovery Service
Recovers missing track durations from MusicBrainz, Spotify, or Discogs.
"""

from typing import Optional
from ....models.releases import Track, ReleaseInfo
from ....models.song import SongData
from ....utils.file_duration_reader import format_duration_ms
from ..identity import (
    select_best_release_match,
    text_similarity,
    track_titles_match,
)


class DurationRecoveryService:
    """Service to recover missing track durations from external sources."""

    def __init__(
        self,
        musicbrainz_client=None,
        spotify_client=None,
        discogs_client=None,
    ):
        if any(
            client is None
            for client in (
                musicbrainz_client,
                spotify_client,
                discogs_client,
            )
        ):
            raise ValueError(
                "DurationRecoveryService requires all provider clients"
            )
        self.musicbrainz_client = musicbrainz_client
        self.spotify_client = spotify_client
        self.discogs_client = discogs_client

    def recover_track_duration(
        self,
        track: Track,
        release_info: ReleaseInfo
    ) -> Optional[str]:
        """
        Try to recover a track's duration from external sources.

        Tries sources in order:
        1. MusicBrainz (using MBID if available, otherwise search)
        2. Spotify (search for track)
        3. Discogs (search release and find track)

        Args:
            track: Track object with missing duration
            release_info: ReleaseInfo object for context (artist, album, etc.)

        Returns:
            Duration string in MM:SS format if found, None otherwise
        """
        # Skip if track already has duration
        if track.duration:
            return track.duration

        # Try MusicBrainz first
        duration = self._try_musicbrainz(track, release_info)
        if duration:
            return duration

        # Try Spotify
        duration = self._try_spotify(track, release_info)
        if duration:
            return duration

        # Try Discogs
        duration = self._try_discogs(track, release_info)
        if duration:
            return duration

        return None

    def recover_release_durations(self, release_info: ReleaseInfo) -> ReleaseInfo:
        """
        Recover durations for all tracks in a release that are missing durations.

        Args:
            release_info: ReleaseInfo object with tracks

        Returns:
            ReleaseInfo with updated track durations
        """
        for track in release_info.tracks:
            if not track.duration:
                duration = self.recover_track_duration(track, release_info)
                if duration:
                    track.duration = duration

        return release_info

    def _try_musicbrainz(
        self,
        track: Track,
        release_info: ReleaseInfo
    ) -> Optional[str]:
        """Try to get duration from MusicBrainz."""
        try:
            # If track has MBID, try to get recording directly
            if track.mbid:
                duration = self._get_recording_by_mbid(track.mbid)
                if duration:
                    return duration

            # Otherwise, search for the recording
            song_data = SongData(
                title=track.title,
                artist=track.artist or release_info.artist,
                album=release_info.title,
                release_year=self._extract_year(release_info.release_date)
            )

            recordings = self.musicbrainz_client.search_recording(song_data, limit=5)
            matching_recordings = [
                recording
                for recording in recordings
                if self._recording_matches(recording, track, release_info)
            ]
            if matching_recordings:
                best_match = max(
                    matching_recordings,
                    key=lambda recording: recording.score or 0,
                )
                if best_match.mbid:
                    duration = self._get_recording_by_mbid(best_match.mbid)
                    if duration:
                        return duration
        except Exception:
            pass

        return None

    def _get_recording_by_mbid(self, mbid: str) -> Optional[str]:
        """Get recording duration by MBID from MusicBrainz."""
        try:
            url = f"{self.musicbrainz_client.base_url}/recording/{mbid}"
            params = {
                'fmt': 'json',
                'inc': 'releases'
            }

            data = self.musicbrainz_client._make_request(url, params)
            if data and 'length' in data and data['length']:
                return format_duration_ms(data['length'])
        except Exception:
            pass

        return None

    def _try_spotify(
        self,
        track: Track,
        release_info: ReleaseInfo
    ) -> Optional[str]:
        """Try to get duration from Spotify."""
        try:
            if not self.spotify_client.access_token:
                return None

            # Search for track
            query = f"track:{track.title} artist:{track.artist or release_info.artist}"
            tracks = self.spotify_client.search_items(query, "track", limit=5)
            matching_tracks = [
                candidate
                for candidate in tracks
                if self._spotify_track_matches(candidate, track, release_info)
            ]
            if matching_tracks:
                duration_ms = matching_tracks[0].get('duration_ms', 0)
                if duration_ms:
                    return format_duration_ms(duration_ms)
        except Exception:
            pass

        return None

    def _try_discogs(
        self,
        track: Track,
        release_info: ReleaseInfo
    ) -> Optional[str]:
        """Try to get duration from Discogs."""
        try:
            # Search for the release (album), not the track
            # Use empty string for title since we're searching by album/artist
            song_data = SongData(
                title="",  # Empty - searching by album/artist only
                artist=release_info.artist,
                album=release_info.title,
                release_year=self._extract_year(release_info.release_date)
            )

            releases = self.discogs_client.search_release(song_data, limit=5)
            if releases:
                matching_release = select_best_release_match(
                    releases,
                    expected_album=release_info.title,
                    expected_artist=release_info.artist,
                    expected_year=self._extract_year(release_info.release_date),
                )
                release_id = (
                    matching_release.discogs_id
                    if matching_release is not None
                    else None
                )
                if release_id:
                    release_details = self.discogs_client.get_release_info(release_id)
                    if release_details:
                        # Find matching track in the release
                        for release_track in release_details.tracks:
                            if (
                                track_titles_match(
                                    track.title,
                                    release_track.title,
                                )
                                and release_track.duration
                            ):
                                return release_track.duration
        except Exception:
            pass

        return None

    @staticmethod
    def _recording_matches(recording, track: Track, release_info: ReleaseInfo) -> bool:
        """Require recording identity before trusting its duration."""
        if not track_titles_match(track.title, recording.title):
            return False

        expected_artist = track.artist or release_info.artist
        if text_similarity(expected_artist, recording.artist) < 0.82:
            return False

        if recording.album and release_info.title:
            return text_similarity(release_info.title, recording.album) >= 0.82
        return True

    @staticmethod
    def _spotify_track_matches(candidate, track: Track, release_info: ReleaseInfo) -> bool:
        """Require Spotify track, artist, and album identity."""
        if not track_titles_match(track.title, candidate.get('name', '')):
            return False

        artists = candidate.get('artists', [])
        candidate_artist = artists[0].get('name', '') if artists else ''
        expected_artist = track.artist or release_info.artist
        if text_similarity(expected_artist, candidate_artist) < 0.82:
            return False

        candidate_album = candidate.get('album', {}).get('name', '')
        if candidate_album and release_info.title:
            return text_similarity(release_info.title, candidate_album) >= 0.82
        return True

    def _extract_year(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None

        try:
            # Try to extract year (format: YYYY-MM-DD or YYYY)
            year_str = date_str[:4]
            return int(year_str)
        except (ValueError, IndexError):
            return None
