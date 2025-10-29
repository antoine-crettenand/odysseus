#!/usr/bin/env python3
"""
Metadata Merger Module
Collects metadata from various sources (MusicBrainz, YouTube) and selects the best metadata
to apply to audio files.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import logging
import requests
from musicbrainz_client import MusicBrainzSong, SongData
from youtube_client import YouTubeVideo
from discogs_client import DiscogsRelease, DiscogsClient
from lastfm_client import LastFmTrack, LastFmClient
from spotify_client import SpotifyTrack, SpotifyClient
from genius_client import GeniusSong, GeniusClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AudioMetadata:
    """Represents audio file metadata."""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    total_discs: Optional[int] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    comment: Optional[str] = None
    composer: Optional[str] = None
    conductor: Optional[str] = None
    performer: Optional[str] = None
    publisher: Optional[str] = None
    copyright: Optional[str] = None
    isrc: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None
    mood: Optional[str] = None
    cover_art_url: Optional[str] = None  # URL to cover art image
    cover_art_data: Optional[bytes] = None  # Cover art image data
    source: str = "unknown"  # Track which source provided this metadata
    
    def __post_init__(self):
        """Validate metadata after initialization."""
        if self.year and not (1900 <= self.year <= 2030):
            logger.warning(f"Invalid year: {self.year}")
            self.year = None
        
        if self.track_number and self.track_number < 1:
            logger.warning(f"Invalid track number: {self.track_number}")
            self.track_number = None
            
        if self.total_tracks and self.total_tracks < 1:
            logger.warning(f"Invalid total tracks: {self.total_tracks}")
            self.total_tracks = None

@dataclass
class MetadataSource:
    """Represents metadata from a specific source."""
    source_name: str
    metadata: AudioMetadata
    confidence: float = 1.0  # Confidence score (0.0 to 1.0)
    completeness: float = 0.0  # How complete the metadata is (0.0 to 1.0)
    
    def __post_init__(self):
        """Calculate completeness score."""
        self.completeness = self._calculate_completeness()
    
    def _calculate_completeness(self) -> float:
        """Calculate how complete the metadata is."""
        fields = [
            self.metadata.title, self.metadata.artist, self.metadata.album,
            self.metadata.year, self.metadata.genre, self.metadata.track_number,
            self.metadata.composer, self.metadata.publisher
        ]
        filled_fields = sum(1 for field in fields if field is not None)
        return filled_fields / len(fields)

class MetadataMerger:
    """Merges metadata from multiple sources and selects the best combination."""
    
    def __init__(self, 
                 discogs_token: Optional[str] = None,
                 lastfm_api_key: Optional[str] = None,
                 spotify_client_id: Optional[str] = None,
                 spotify_client_secret: Optional[str] = None,
                 genius_access_token: Optional[str] = None):
        self.sources: List[MetadataSource] = []
        self.final_metadata: Optional[AudioMetadata] = None
        
        # Initialize clients
        self.discogs_client = DiscogsClient(discogs_token) if discogs_token else None
        self.lastfm_client = LastFmClient(lastfm_api_key) if lastfm_api_key else None
        self.spotify_client = SpotifyClient(spotify_client_id, spotify_client_secret) if spotify_client_id and spotify_client_secret else None
        self.genius_client = GeniusClient(genius_access_token) if genius_access_token else None
    

    def add_songdata_metadata(self, song_data: SongData) -> None:
        metadata = AudioMetadata(
            title=song_data.title,
            artist=song_data.artist,
            album=song_data.album,
            year=self._extract_year_from_date(song_data.release_date),
            genre=song_data.genre,
            source="songdata"
        )
        self.sources.append(MetadataSource(
            source_name="SongData",
            metadata=metadata,
            confidence=0.7
        ))
    
    def add_musicbrainz_metadata(self, musicbrainz_result: MusicBrainzSong) -> None:
        """Add MusicBrainz metadata to the merger."""
        metadata = AudioMetadata(
            title=musicbrainz_result.title,
            artist=musicbrainz_result.artist,
            album=musicbrainz_result.album,
            year=self._extract_year_from_date(musicbrainz_result.release_date),
            genre=musicbrainz_result.genre,
            source="musicbrainz"
        )
        
        # Try to get cover art from MusicBrainz
        if musicbrainz_result.mbid:
            cover_art_url = self._get_musicbrainz_cover_art_url(musicbrainz_result.mbid)
            if cover_art_url:
                metadata.cover_art_url = cover_art_url
                # Download the cover art
                cover_art_data = self._download_cover_art(cover_art_url)
                if cover_art_data:
                    metadata.cover_art_data = cover_art_data
                    logger.info(f"Downloaded cover art from MusicBrainz: {len(cover_art_data)} bytes")
        
        # MusicBrainz typically has high confidence for basic metadata
        confidence = 0.9
        if musicbrainz_result.score and musicbrainz_result.score > 80:
            confidence = 0.95
        elif musicbrainz_result.score and musicbrainz_result.score < 60:
            confidence = 0.8
        
        source = MetadataSource(
            source_name="MusicBrainz",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added MusicBrainz metadata: {metadata.title} by {metadata.artist}")
    
    def add_youtube_metadata(self, youtube_video: YouTubeVideo) -> None:
        """Add YouTube metadata to the merger."""
        metadata = AudioMetadata(
            title=youtube_video.title,
            artist=youtube_video.channel,  # YouTube channel as artist
            genre=None,  # YouTube videos don't have genre information
            source="youtube"
        )
        
        # YouTube metadata is generally less reliable for music metadata
        confidence = 0.6
        
        # Try to extract artist from title if it contains " - " pattern
        if youtube_video.title and " - " in youtube_video.title:
            parts = youtube_video.title.split(" - ", 1)
            if len(parts) == 2:
                metadata.artist = parts[0].strip()
                metadata.title = parts[1].strip()
                confidence = 0.7  # Slightly higher confidence if we can parse artist
        
        source = MetadataSource(
            source_name="YouTube",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added YouTube metadata: {metadata.title} by {metadata.artist}")
    
    def add_discogs_metadata(self, discogs_result: DiscogsRelease) -> None:
        """Add Discogs metadata to the merger."""
        metadata = AudioMetadata(
            title=discogs_result.title,
            artist=discogs_result.artist,
            album=discogs_result.album,
            year=discogs_result.year,
            genre=discogs_result.genre,
            cover_art_url=discogs_result.cover_art_url,
            source="discogs"
        )
        
        # Discogs typically has very high confidence for release data
        confidence = 0.95
        
        # Download cover art if available
        if discogs_result.cover_art_url:
            cover_art_data = self._download_cover_art(discogs_result.cover_art_url)
            if cover_art_data:
                metadata.cover_art_data = cover_art_data
                logger.info(f"Downloaded cover art from Discogs: {len(cover_art_data)} bytes")
        
        source = MetadataSource(
            source_name="Discogs",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added Discogs metadata: {metadata.title} by {metadata.artist}")
    
    def add_lastfm_metadata(self, lastfm_result: LastFmTrack) -> None:
        """Add Last.fm metadata to the merger."""
        metadata = AudioMetadata(
            title=lastfm_result.title,
            artist=lastfm_result.artist,
            album=lastfm_result.album,
            source="lastfm"
        )
        
        # Last.fm confidence based on popularity metrics
        confidence = 0.7
        if lastfm_result.playcount and lastfm_result.playcount > 10000:
            confidence = 0.85
        elif lastfm_result.listeners and lastfm_result.listeners > 1000:
            confidence = 0.8
        
        # Add popularity as comment
        if lastfm_result.playcount:
            metadata.comment = f"Last.fm playcount: {lastfm_result.playcount:,}"
        
        # Add tags as genre if available
        if lastfm_result.tags:
            metadata.genre = ', '.join(lastfm_result.tags[:3])  # Top 3 tags
        
        source = MetadataSource(
            source_name="Last.fm",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added Last.fm metadata: {metadata.title} by {metadata.artist}")
    
    def add_spotify_metadata(self, spotify_result: SpotifyTrack) -> None:
        """Add Spotify metadata to the merger."""
        metadata = AudioMetadata(
            title=spotify_result.title,
            artist=spotify_result.artist,
            album=spotify_result.album,
            year=spotify_result.year,
            genre=spotify_result.genre,
            cover_art_url=spotify_result.cover_art_url,
            source="spotify"
        )
        
        # Spotify confidence based on popularity
        confidence = 0.8
        if spotify_result.popularity:
            if spotify_result.popularity > 70:
                confidence = 0.9
            elif spotify_result.popularity > 40:
                confidence = 0.85
            elif spotify_result.popularity < 20:
                confidence = 0.75
        
        # Download cover art if available
        if spotify_result.cover_art_url:
            cover_art_data = self._download_cover_art(spotify_result.cover_art_url)
            if cover_art_data:
                metadata.cover_art_data = cover_art_data
                logger.info(f"Downloaded cover art from Spotify: {len(cover_art_data)} bytes")
        
        # Add audio features as comment if available
        if spotify_result.audio_features:
            features = spotify_result.audio_features
            feature_text = f"BPM: {features.get('tempo', 'N/A')}, Key: {features.get('key', 'N/A')}, Energy: {features.get('energy', 'N/A')}"
            metadata.comment = feature_text
        
        source = MetadataSource(
            source_name="Spotify",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added Spotify metadata: {metadata.title} by {metadata.artist}")
    
    def add_genius_metadata(self, genius_result: GeniusSong) -> None:
        """Add Genius metadata to the merger."""
        metadata = AudioMetadata(
            title=genius_result.title,
            artist=genius_result.artist,
            album=genius_result.album,
            year=genius_result.year,
            source="genius"
        )
        
        # Genius confidence based on available data
        confidence = 0.75
        if genius_result.lyrics:
            confidence = 0.85
        if genius_result.description:
            confidence = 0.8
        
        # Add description as comment
        if genius_result.description:
            metadata.comment = genius_result.description[:200] + "..." if len(genius_result.description) > 200 else genius_result.description
        
        # Use song art as cover art
        if genius_result.song_art_image_url:
            metadata.cover_art_url = genius_result.song_art_image_url
            cover_art_data = self._download_cover_art(genius_result.song_art_image_url)
            if cover_art_data:
                metadata.cover_art_data = cover_art_data
                logger.info(f"Downloaded cover art from Genius: {len(cover_art_data)} bytes")
        
        source = MetadataSource(
            source_name="Genius",
            metadata=metadata,
            confidence=confidence
        )
        
        self.sources.append(source)
        logger.info(f"Added Genius metadata: {metadata.title} by {metadata.artist}")
    
    def search_all_sources(self, title: str, artist: str, album: Optional[str] = None) -> None:
        """Search all available sources for metadata."""
        logger.info(f"Searching all sources for: {title} by {artist}")
        
        # Search Discogs
        if self.discogs_client:
            try:
                discogs_results = self.discogs_client.search_release(title, artist, album)
                if discogs_results:
                    self.add_discogs_metadata(discogs_results[0])  # Take first result
            except Exception as e:
                logger.warning(f"Discogs search failed: {e}")
        
        # Search Last.fm
        if self.lastfm_client:
            try:
                lastfm_results = self.lastfm_client.search_track(title, artist, album)
                if lastfm_results:
                    self.add_lastfm_metadata(lastfm_results[0])  # Take first result
            except Exception as e:
                logger.warning(f"Last.fm search failed: {e}")
        
        # Search Spotify
        if self.spotify_client:
            try:
                spotify_results = self.spotify_client.search_tracks(title, artist, album)
                if spotify_results:
                    # Get audio features for the first result
                    spotify_track = spotify_results[0]
                    audio_features = self.spotify_client.get_track_audio_features(spotify_track.spotify_id)
                    if audio_features:
                        spotify_track.audio_features = audio_features
                    self.add_spotify_metadata(spotify_track)
            except Exception as e:
                logger.warning(f"Spotify search failed: {e}")
        
        # Search Genius
        if self.genius_client:
            try:
                genius_results = self.genius_client.search_songs(title, artist)
                if genius_results:
                    # Get detailed info including lyrics
                    genius_song = genius_results[0]
                    detailed_song = self.genius_client.get_song_details(genius_song.genius_id)
                    if detailed_song:
                        genius_song = detailed_song
                    self.add_genius_metadata(genius_song)
            except Exception as e:
                logger.warning(f"Genius search failed: {e}")
    
    def merge_metadata(self) -> AudioMetadata:
        """Merge metadata from all sources and return the best combination."""
        if not self.sources:
            logger.warning("No metadata sources available")
            return AudioMetadata()
        
        # Sort sources by combined score (confidence * completeness)
        sorted_sources = sorted(
            self.sources,
            key=lambda s: s.confidence * s.completeness,
            reverse=True
        )
        
        # Start with the best source as base
        best_source = sorted_sources[0]
        merged_metadata = AudioMetadata(
            title=best_source.metadata.title,
            artist=best_source.metadata.artist,
            album=best_source.metadata.album,
            album_artist=best_source.metadata.album_artist,
            track_number=best_source.metadata.track_number,
            total_tracks=best_source.metadata.total_tracks,
            disc_number=best_source.metadata.disc_number,
            total_discs=best_source.metadata.total_discs,
            year=best_source.metadata.year,
            genre=best_source.metadata.genre,
            comment=best_source.metadata.comment,
            composer=best_source.metadata.composer,
            conductor=best_source.metadata.conductor,
            performer=best_source.metadata.performer,
            publisher=best_source.metadata.publisher,
            copyright=best_source.metadata.copyright,
            isrc=best_source.metadata.isrc,
            bpm=best_source.metadata.bpm,
            key=best_source.metadata.key,
            mood=best_source.metadata.mood,
            source=f"merged_from_{best_source.source_name}"
        )
        
        # Fill in missing fields from other sources
        for source in sorted_sources[1:]:
            self._fill_missing_fields(merged_metadata, source.metadata, source.confidence)
        
        # Handle cover art merging - prefer MusicBrainz over YouTube
        for source in sorted_sources:
            if source.metadata.cover_art_data and not merged_metadata.cover_art_data:
                merged_metadata.cover_art_data = source.metadata.cover_art_data
                merged_metadata.cover_art_url = source.metadata.cover_art_url
                break
        
        self.final_metadata = merged_metadata
        logger.info(f"Merged metadata: {merged_metadata.title} by {merged_metadata.artist}")
        return merged_metadata
    
    def _fill_missing_fields(self, target: AudioMetadata, source: AudioMetadata, confidence: float) -> None:
        """Fill missing fields in target metadata from source metadata."""
        # Only fill fields that are None in target and have a value in source
        # Use confidence threshold to decide whether to use the source value
        confidence_threshold = 0.5
        
        if confidence >= confidence_threshold:
            if target.title is None and source.title is not None:
                target.title = source.title
            if target.artist is None and source.artist is not None:
                target.artist = source.artist
            if target.album is None and source.album is not None:
                target.album = source.album
            if target.year is None and source.year is not None:
                target.year = source.year
            if target.genre is None and source.genre is not None:
                target.genre = source.genre
    
    def _extract_year_from_date(self, date_str: Optional[str]) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None
        
        try:
            # Try to extract year from various date formats
            if "-" in date_str:
                year_part = date_str.split("-")[0]
                return int(year_part)
            elif len(date_str) >= 4:
                return int(date_str[:4])
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _download_cover_art(self, url: str) -> Optional[bytes]:
        """Download cover art from URL."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                logger.warning(f"URL does not point to an image: {url}")
                return None
            
            # Check file size (max 10MB)
            if len(response.content) > 10 * 1024 * 1024:
                logger.warning(f"Cover art too large: {len(response.content)} bytes")
                return None
            
            logger.info(f"Downloaded cover art: {len(response.content)} bytes")
            return response.content
            
        except Exception as e:
            logger.error(f"Error downloading cover art from {url}: {e}")
            return None
    
    def _get_musicbrainz_cover_art_url(self, mbid: str) -> Optional[str]:
        """Get cover art URL from MusicBrainz using Cover Art Archive."""
        try:
            # Use Cover Art Archive API
            cover_art_url = f"http://coverartarchive.org/release/{mbid}"
            
            response = requests.get(cover_art_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                
                # Look for front cover
                for image in images:
                    if image.get('front', False):
                        return image.get('image')
                
                # If no front cover, use first image
                if images:
                    return images[0].get('image')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting MusicBrainz cover art for {mbid}: {e}")
            return None
    
    def _get_youtube_thumbnail_url(self, video_id: str) -> Optional[str]:
        """Get high-quality thumbnail URL from YouTube video ID."""
        # YouTube provides different thumbnail qualities
        # maxresdefault is the highest quality (1280x720)
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    
    def get_metadata_summary(self) -> Dict[str, Any]:
        """Get a summary of all metadata sources and the final merged result."""
        summary = {
            "sources": [],
            "final_metadata": None,
            "total_sources": len(self.sources)
        }
        
        for source in self.sources:
            summary["sources"].append({
                "name": source.source_name,
                "confidence": source.confidence,
                "completeness": source.completeness,
                "metadata": {
                    "title": source.metadata.title,
                    "artist": source.metadata.artist,
                    "album": source.metadata.album,
                    "year": source.metadata.year
                }
            })
        
        if self.final_metadata:
            summary["final_metadata"] = {
                "title": self.final_metadata.title,
                "artist": self.final_metadata.artist,
                "album": self.final_metadata.album,
                "year": self.final_metadata.year,
                "genre": self.final_metadata.genre,
                "source": self.final_metadata.source,
                "has_cover_art": self.final_metadata.cover_art_data is not None,
                "cover_art_size": len(self.final_metadata.cover_art_data) if self.final_metadata.cover_art_data else 0
            }
        
        return summary
    
    def display_metadata_sources(self) -> None:
        """Display all metadata sources in a formatted way for user selection."""
        if not self.sources:
            print("No metadata sources available.")
            return
        
        print("\n" + "="*80)
        print("METADATA SOURCES")
        print("="*80)
        
        for i, source in enumerate(self.sources, 1):
            print(f"\n{i}. {source.source_name}")
            print(f"   Confidence: {source.confidence:.2f} | Completeness: {source.completeness:.2f}")
            print(f"   Title: {source.metadata.title or 'N/A'}")
            print(f"   Artist: {source.metadata.artist or 'N/A'}")
            print(f"   Album: {source.metadata.album or 'N/A'}")
            print(f"   Year: {source.metadata.year or 'N/A'}")
            if source.metadata.genre:
                print(f"   Genre: {source.metadata.genre}")
            if source.metadata.cover_art_url:
                print(f"   Cover Art: Available")
            print("-" * 40)
    
    def get_user_metadata_selection(self) -> AudioMetadata:
        """Allow user to select metadata from available sources."""
        if not self.sources:
            print("No metadata sources available.")
            return AudioMetadata()
        
        self.display_metadata_sources()
        
        # Get user selection for each field
        selected_metadata = AudioMetadata()
        
        print("\n" + "="*80)
        print("METADATA SELECTION")
        print("="*80)
        print("Choose the source for each metadata field (or press Enter to skip):")
        
        # Title selection
        title_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.title]
        if title_options:
            print(f"\nTitle options:")
            for i, source in title_options:
                print(f"  {i}. {source.metadata.title} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select title (1-{len(title_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(title_options):
                        selected_metadata.title = title_options[choice_num - 1][1].metadata.title
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(title_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Artist selection
        artist_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.artist]
        if artist_options:
            print(f"\nArtist options:")
            for i, source in artist_options:
                print(f"  {i}. {source.metadata.artist} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select artist (1-{len(artist_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(artist_options):
                        selected_metadata.artist = artist_options[choice_num - 1][1].metadata.artist
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(artist_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Album selection
        album_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.album]
        if album_options:
            print(f"\nAlbum/Release options:")
            for i, source in album_options:
                print(f"  {i}. {source.metadata.album} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select album (1-{len(album_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(album_options):
                        selected_metadata.album = album_options[choice_num - 1][1].metadata.album
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(album_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Year selection
        year_options = [(i, source) for i, source in enumerate(self.sources, 1) if source.metadata.year]
        if year_options:
            print(f"\nYear options:")
            for i, source in year_options:
                print(f"  {i}. {source.metadata.year} (from {source.source_name})")
            
            while True:
                try:
                    choice = input(f"Select year (1-{len(year_options)}) or Enter to skip: ").strip()
                    if not choice:
                        break
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(year_options):
                        selected_metadata.year = year_options[choice_num - 1][1].metadata.year
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(year_options)}")
                except ValueError:
                    print("Please enter a valid number or press Enter to skip")
        
        # Copy cover art from the first available source
        for source in self.sources:
            if source.metadata.cover_art_data:
                selected_metadata.cover_art_data = source.metadata.cover_art_data
                selected_metadata.cover_art_url = source.metadata.cover_art_url
                break
        
        # Set source as manual selection
        selected_metadata.source = "manual_selection"
        
        print(f"\nSelected metadata:")
        print(f"  Title: {selected_metadata.title or 'N/A'}")
        print(f"  Artist: {selected_metadata.artist or 'N/A'}")
        print(f"  Album: {selected_metadata.album or 'N/A'}")
        print(f"  Year: {selected_metadata.year or 'N/A'}")
        if selected_metadata.cover_art_data:
            print(f"  Cover Art: Available ({len(selected_metadata.cover_art_data)} bytes)")
        
        return selected_metadata
    
    def set_final_metadata(self, metadata: AudioMetadata) -> None:
        """Set the final metadata manually (e.g., from user selection)."""
        self.final_metadata = metadata
        logger.info(f"Set final metadata manually: {metadata.title} by {metadata.artist}")
    
    def apply_metadata_to_file(self, file_path: Path) -> bool:
        """Apply the merged metadata to an audio file."""
        if not self.final_metadata:
            logger.error("No merged metadata available")
            return False
        
        try:
            # Try to import mutagen for metadata writing
            from mutagen import File as MutagenFile
            from mutagen.id3 import ID3, TIT2, TPE1, TALB, TYER, TCON, TPE2, TRCK, TPOS, APIC
            
            audio_file = MutagenFile(str(file_path))
            if audio_file is None:
                logger.error(f"Could not load audio file: {file_path}")
                return False
            
            # Apply metadata
            if self.final_metadata.title:
                audio_file['title'] = self.final_metadata.title
            if self.final_metadata.artist:
                audio_file['artist'] = self.final_metadata.artist
            if self.final_metadata.album:
                audio_file['album'] = self.final_metadata.album
            if self.final_metadata.year:
                audio_file['date'] = str(self.final_metadata.year)
            if self.final_metadata.genre:
                audio_file['genre'] = self.final_metadata.genre
            
            # Apply cover art if available
            if self.final_metadata.cover_art_data:
                try:
                    # Determine MIME type from cover art data
                    mime_type = "image/jpeg"  # Default to JPEG
                    if self.final_metadata.cover_art_data.startswith(b'\xff\xd8\xff'):
                        mime_type = "image/jpeg"
                    elif self.final_metadata.cover_art_data.startswith(b'\x89PNG'):
                        mime_type = "image/png"
                    
                    # Add cover art to ID3 tags
                    if hasattr(audio_file, 'tags') and audio_file.tags is not None:
                        # For MP3 files with ID3 tags
                        apic = APIC(
                            encoding=3,  # UTF-8
                            mime=mime_type,
                            type=3,  # Cover (front)
                            desc='Cover',
                            data=self.final_metadata.cover_art_data
                        )
                        audio_file.tags.add(apic)
                        logger.info(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                    else:
                        # For other formats, try to add as generic picture
                        audio_file['picture'] = self.final_metadata.cover_art_data
                        logger.info(f"Added cover art to {file_path} ({len(self.final_metadata.cover_art_data)} bytes)")
                        
                except Exception as e:
                    logger.warning(f"Could not add cover art to {file_path}: {e}")
            
            # Save the file
            audio_file.save()
            logger.info(f"Applied metadata to {file_path}")
            return True
            
        except ImportError:
            logger.error("mutagen library not available. Install with: pip install mutagen")
            return False
        except Exception as e:
            logger.error(f"Error applying metadata to {file_path}: {e}")
            return False
