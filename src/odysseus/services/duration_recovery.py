"""
Duration Recovery Service
Recovers missing track durations from MusicBrainz, Spotify, or Discogs.
"""

import requests
from typing import Optional
from ..models.releases import Track, ReleaseInfo
from ..models.song import SongData
from ..clients.musicbrainz import MusicBrainzClient
from ..clients.spotify import SpotifyClient
from ..clients.discogs import DiscogsClient


class DurationRecoveryService:
    """Service to recover missing track durations from external sources."""
    
    def __init__(self):
        self.musicbrainz_client = MusicBrainzClient()
        self.spotify_client = SpotifyClient()
        self.discogs_client = DiscogsClient()
    
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
            if recordings:
                # Use the first result's duration
                # Note: MusicBrainzSong doesn't have duration, so we need to get the recording
                # For now, we'll search and get the first recording's MBID, then fetch it
                if recordings[0].mbid:
                    duration = self._get_recording_by_mbid(recordings[0].mbid)
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
                return self.musicbrainz_client._format_duration(data['length'])
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
            url = f"{self.spotify_client.base_url}/search"
            headers = self.spotify_client._get_headers()
            params = {
                'q': query,
                'type': 'track',
                'limit': 5
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=self.spotify_client.timeout)
            if response.status_code == 200:
                data = response.json()
                tracks = data.get('tracks', {}).get('items', [])
                
                if tracks:
                    # Use the first result
                    duration_ms = tracks[0].get('duration_ms', 0)
                    if duration_ms:
                        return self.spotify_client._format_duration(duration_ms)
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
                # Get the first release's details
                release_id = releases[0].discogs_id  # Discogs uses discogs_id field
                if release_id:
                    release_details = self.discogs_client.get_release_info(release_id)
                    if release_details:
                        # Find matching track in the release
                        for release_track in release_details.tracks:
                            if (release_track.title.lower() == track.title.lower() and
                                release_track.duration):
                                return release_track.duration
        except Exception:
            pass
        
        return None
    
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

