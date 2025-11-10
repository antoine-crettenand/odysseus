"""
Cover art fetching service for retrieving cover art from various sources.
"""

import requests
from typing import Optional, Dict
from pathlib import Path
from ..models.releases import ReleaseInfo


class CoverArtFetcher:
    """Service for fetching cover art from various sources."""
    
    def __init__(self):
        # Cache for cover art to avoid fetching the same cover art multiple times
        # Key: (release_mbid or cover_art_url), Value: cover_art_data (bytes)
        self._cover_art_cache: Dict[str, Optional[bytes]] = {}
        # Cache for Discogs search results to avoid repeated searches
        # Key: (artist, album), Value: cover_art_url (str) or None
        self._discogs_search_cache: Dict[tuple, Optional[str]] = {}
    
    def fetch_cover_art_from_url(self, url: str, console=None, use_cache: bool = True) -> Optional[bytes]:
        """
        Fetch cover art from a URL (e.g., Spotify).
        
        Args:
            url: URL to fetch cover art from
            console: Optional console for output
            use_cache: Whether to use cached cover art if available
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        if not url:
            return None
        
        # Check cache first
        if use_cache and url in self._cover_art_cache:
            cached_data = self._cover_art_cache[url]
            if cached_data is not None and console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Using cached cover art from URL ({len(cached_data)} bytes)[/dim]")
            return cached_data
        
        try:
            headers = {
                'User-Agent': 'Odysseus/1.0'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                if console:
                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetched cover art from URL ({len(response.content)} bytes)[/dim]")
                # Cache the result
                if use_cache:
                    self._cover_art_cache[url] = response.content
                return response.content
            else:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Failed to fetch cover art from URL: HTTP {response.status_code}")
                # Cache the failure (None) to avoid retrying
                if use_cache:
                    self._cover_art_cache[url] = None
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error fetching cover art from URL: {e}")
            # Cache the failure
            if use_cache:
                self._cover_art_cache[url] = None
        
        return None
    
    def fetch_cover_art(self, mbid: str, console=None, use_cache: bool = True) -> Optional[bytes]:
        """
        Fetch cover art from MusicBrainz Cover Art Archive.
        
        Args:
            mbid: MusicBrainz release ID
            console: Optional console for output
            use_cache: Whether to use cached cover art if available
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        if not mbid or not mbid.strip():
            if console:
                console.print(f"[yellow]⚠[/yellow] No MBID provided for cover art fetch")
            return None
        
        # Check cache first
        cache_key = f"mbid:{mbid}"
        if use_cache and cache_key in self._cover_art_cache:
            cached_data = self._cover_art_cache[cache_key]
            if cached_data is not None and console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Using cached cover art from MusicBrainz ({len(cached_data)} bytes)[/dim]")
            return cached_data
            
        try:
            # Use HTTPS and add User-Agent header
            cover_art_url = f"https://coverartarchive.org/release/{mbid}"
            headers = {
                'User-Agent': 'Odysseus/1.0 (https://github.com/antoinecrettenand/odysseus)'
            }
            response = requests.get(cover_art_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])
                
                if not images:
                    if console:
                        console.print(f"[yellow]⚠[/yellow] No images found in Cover Art Archive for MBID: {mbid}")
                    # Cache the failure
                    if use_cache:
                        self._cover_art_cache[cache_key] = None
                    return None
                
                # Look for front cover
                for image in images:
                    if image.get('front', False):
                        image_url = image.get('image')
                        if image_url:
                            img_response = requests.get(image_url, headers=headers, timeout=10)
                            if img_response.status_code == 200:
                                if console:
                                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetched front cover art ({len(img_response.content)} bytes)[/dim]")
                                # Cache the result
                                if use_cache:
                                    self._cover_art_cache[cache_key] = img_response.content
                                return img_response.content
                
                # If no front cover, use first image
                if images:
                    image_url = images[0].get('image')
                    if image_url:
                        img_response = requests.get(image_url, headers=headers, timeout=10)
                        if img_response.status_code == 200:
                            if console:
                                console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetched cover art (first available, {len(img_response.content)} bytes)[/dim]")
                            # Cache the result
                            if use_cache:
                                self._cover_art_cache[cache_key] = img_response.content
                            return img_response.content
            elif response.status_code == 404:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Cover art not found in archive for MBID: {mbid}")
                # Cache the failure
                if use_cache:
                    self._cover_art_cache[cache_key] = None
            else:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Cover Art Archive returned status {response.status_code} for MBID: {mbid}")
                # Cache the failure
                if use_cache:
                    self._cover_art_cache[cache_key] = None
        except requests.exceptions.RequestException as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Network error fetching cover art: {e}")
            # Cache the failure
            if use_cache:
                self._cover_art_cache[cache_key] = None
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error fetching cover art: {e}")
            # Cache the failure
            if use_cache:
                self._cover_art_cache[cache_key] = None
        return None
    
    def _fetch_cover_art_from_discogs(self, release_info: ReleaseInfo, console=None) -> Optional[bytes]:
        """
        Search Discogs for the release and fetch cover art.
        
        Uses caching to avoid repeated searches for the same release.
        
        Args:
            release_info: Release information
            console: Optional console for output
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        try:
            from ..clients.discogs import DiscogsClient
            from ..models.song import SongData
            
            # Create cache key from artist and album
            artist = (release_info.artist or "").lower().strip()
            album = (release_info.title or "").lower().strip()
            cache_key = (artist, album)
            
            # Check cache first
            if cache_key in self._discogs_search_cache:
                cached_url = self._discogs_search_cache[cache_key]
                if cached_url is None:
                    # Cached as "not found" - return None
                    return None
                # Use cached URL
                if console:
                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Using cached Discogs cover art URL[/dim]")
                cover_art_data = self.fetch_cover_art_from_url(cached_url, console)
                if cover_art_data:
                    if console:
                        console.print(f"[green]✓ Got cover art from Discogs ({len(cover_art_data)} bytes)[/green]")
                    return cover_art_data
                # If cached URL fails, remove from cache and continue to search
                del self._discogs_search_cache[cache_key]
            
            # Not in cache, need to search
            if console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Trying to find cover art from Discogs...[/dim]")
            
            discogs_client = DiscogsClient()
            
            # Build search query
            song_data = SongData(
                title="",
                artist=release_info.artist or "",
                album=release_info.title or "",
                release_year=int(release_info.release_date[:4]) if release_info.release_date and len(release_info.release_date) >= 4 else None
            )
            
            # Search for releases
            discogs_results = discogs_client.search_release(song_data, limit=5)
            
            if not discogs_results:
                # Cache "not found" result
                self._discogs_search_cache[cache_key] = None
                return None
            
            # Find the best matching release
            for result in discogs_results:
                # Check if it matches our release
                if result.album and release_info.title:
                    # Simple matching - check if album titles are similar
                    if result.album.lower() in release_info.title.lower() or release_info.title.lower() in result.album.lower():
                        # Check if artist matches
                        if result.artist and release_info.artist:
                            if result.artist.lower() in release_info.artist.lower() or release_info.artist.lower() in result.artist.lower():
                                # Found a match, try to get cover art
                                cover_art_url = None
                                
                                if result.cover_art_url:
                                    cover_art_url = result.cover_art_url
                                    if console:
                                        console.print(f"[dim blue]ℹ[/dim blue] [dim]Found Discogs release: {result.album}[/dim]")
                                
                                # If no cover art URL in search result, try to get detailed release info
                                if not cover_art_url and result.discogs_id:
                                    detailed_info = discogs_client.get_release_info(result.discogs_id)
                                    if detailed_info and detailed_info.cover_art_url:
                                        cover_art_url = detailed_info.cover_art_url
                                        if console:
                                            console.print(f"[blue]ℹ[/blue] Found Discogs release: {result.album}")
                                
                                if cover_art_url:
                                    # Cache the URL for future use
                                    self._discogs_search_cache[cache_key] = cover_art_url
                                    
                                    cover_art_data = self.fetch_cover_art_from_url(cover_art_url, console)
                                    if cover_art_data:
                                        if console:
                                            console.print(f"[green]✓ Got cover art from Discogs ({len(cover_art_data)} bytes)[/green]")
                                        return cover_art_data
            
            # Cache "not found" result
            self._discogs_search_cache[cache_key] = None
            return None
            
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error searching Discogs for cover art: {e}")
            return None
    
    def _fetch_cover_art_from_spotify(self, release_info: ReleaseInfo, console=None) -> Optional[bytes]:
        """
        Search Spotify for the release and fetch cover art.
        
        Args:
            release_info: Release information
            console: Optional console for output
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        try:
            from ..clients.spotify import SpotifyClient
            
            spotify_client = SpotifyClient()
            
            # Check if Spotify client is authenticated
            if not spotify_client.access_token:
                # Spotify requires authentication, skip silently
                return None
            
            # Search for album
            query = f"album:{release_info.title} artist:{release_info.artist}"
            if release_info.release_date and len(release_info.release_date) >= 4:
                year = release_info.release_date[:4]
                query += f" year:{year}"
            
            try:
                search_url = f"{spotify_client.base_url}/search"
                headers = spotify_client._get_headers()
                params = {
                    'q': query,
                    'type': 'album',
                    'limit': 5
                }
                
                response = requests.get(search_url, headers=headers, params=params, timeout=10)
                if response.status_code != 200:
                    return None
                
                data = response.json()
                albums = data.get('albums', {}).get('items', [])
                
                if not albums:
                    return None
                
                # Find the best matching album
                for album in albums:
                    album_name = album.get('name', '')
                    artists = album.get('artists', [])
                    artist_name = artists[0].get('name', '') if artists else ''
                    
                    # Check if it matches
                    if album_name.lower() in release_info.title.lower() or release_info.title.lower() in album_name.lower():
                        if artist_name.lower() in release_info.artist.lower() or release_info.artist.lower() in artist_name.lower():
                            # Found a match, get cover art
                            images = album.get('images', [])
                            if images:
                                # Use the largest image (first one is usually the largest)
                                cover_art_url = images[0].get('url')
                                if cover_art_url:
                                    if console:
                                        console.print(f"[dim blue]ℹ[/dim blue] [dim]Found Spotify album: {album_name}[/dim]")
                                    cover_art_data = self.fetch_cover_art_from_url(cover_art_url, console)
                                    if cover_art_data:
                                        if console:
                                            console.print(f"[green]✓ Got cover art from Spotify ({len(cover_art_data)} bytes)[/green]")
                                        return cover_art_data
                
                return None
                
            except Exception as e:
                if console:
                    console.print(f"[yellow]⚠[/yellow] Error searching Spotify: {e}")
                return None
            
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error searching Spotify for cover art: {e}")
            return None
    
    def _extract_cover_art_from_folder(self, folder_path: Path, console=None) -> Optional[bytes]:
        """
        Extract cover art from an existing audio file in the folder.
        
        Args:
            folder_path: Path to the folder containing audio files
            console: Optional console for output
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        try:
            # Look for audio files (MP3, M4A, FLAC, etc.)
            audio_extensions = ['.mp3', '.m4a', '.flac', '.ogg', '.aac']
            existing_files = []
            for ext in audio_extensions:
                existing_files.extend(list(folder_path.glob(f"*{ext}")))
            
            if not existing_files:
                if console:
                    console.print(f"[yellow]⚠[/yellow] No audio files found in folder to extract cover art from")
                return None
            
            # Try each file until we find one with cover art
            for audio_file in existing_files:
                try:
                    # Try with mutagen first (works for MP3, M4A, FLAC, OGG)
                    from mutagen.mp3 import MP3
                    from mutagen.id3 import ID3NoHeaderError
                    from mutagen.mp4 import MP4
                    from mutagen.flac import FLAC
                    
                    file_ext = audio_file.suffix.lower()
                    
                    if file_ext == '.mp3':
                        try:
                            audio = MP3(str(audio_file))
                            if audio.tags:
                                # Look for APIC (cover art) frames
                                for key in audio.tags.keys():
                                    if key.startswith('APIC'):
                                        apic = audio.tags[key]
                                        if hasattr(apic, 'data'):
                                            if console:
                                                console.print(f"[green]✓ Extracted cover art from {audio_file.name} ({len(apic.data)} bytes)[/green]")
                                            return apic.data
                        except ID3NoHeaderError:
                            pass
                    
                    elif file_ext == '.m4a':
                        try:
                            audio = MP4(str(audio_file))
                            if audio.tags and 'covr' in audio.tags:
                                cover = audio.tags['covr'][0]
                                if hasattr(cover, 'data'):
                                    if console:
                                        console.print(f"[green]✓ Extracted cover art from {audio_file.name} ({len(cover.data)} bytes)[/green]")
                                    return cover.data
                        except Exception:
                            pass
                    
                    elif file_ext == '.flac':
                        try:
                            audio = FLAC(str(audio_file))
                            if audio.pictures:
                                picture = audio.pictures[0]
                                if hasattr(picture, 'data'):
                                    if console:
                                        console.print(f"[green]✓ Extracted cover art from {audio_file.name} ({len(picture.data)} bytes)[/green]")
                                    return picture.data
                        except Exception:
                            pass
                    
                    # Try with eyed3 as fallback for MP3
                    if file_ext == '.mp3':
                        try:
                            import eyed3
                            audiofile = eyed3.load(str(audio_file))
                            if audiofile and audiofile.tag and audiofile.tag.images:
                                image = audiofile.tag.images[0]
                                if hasattr(image, 'image_data'):
                                    if console:
                                        console.print(f"[green]✓ Extracted cover art from {audio_file.name} ({len(image.image_data)} bytes)[/green]")
                                    return image.image_data
                        except Exception:
                            pass
                            
                except Exception as e:
                    # Continue to next file if this one fails
                    continue
            
            if console:
                console.print(f"[yellow]⚠[/yellow] No cover art found in existing audio files")
            return None
            
        except Exception as e:
            if console:
                console.print(f"[yellow]⚠[/yellow] Error extracting cover art from folder: {e}")
            return None
    
    def fetch_cover_art_for_release(self, release_info: ReleaseInfo, console=None, folder_path: Optional[Path] = None) -> Optional[bytes]:
        """
        Fetch cover art for a release (optimized to fetch once per release).
        
        This method should be called once per release, and the result can be reused
        for all tracks in that release.
        
        Args:
            release_info: ReleaseInfo object containing release metadata
            console: Optional console for output
            folder_path: Optional path to the release folder (for extracting from existing tracks)
            
        Returns:
            Cover art data as bytes, or None if failed
        """
        # Priority 1: Try Spotify (URL first, then search)
        # First, try Spotify cover art URL if available
        if release_info.cover_art_url:
            if console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetching cover art from Spotify for release...[/dim]")
            cover_art_data = self.fetch_cover_art_from_url(release_info.cover_art_url, console)
            if cover_art_data:
                return cover_art_data
        
        # If no Spotify URL, try searching Spotify
        if console:
            console.print(f"[dim blue]ℹ[/dim blue] [dim]Trying to find cover art from Spotify...[/dim]")
        cover_art_data = self._fetch_cover_art_from_spotify(release_info, console)
        if cover_art_data:
            return cover_art_data
        
        # Priority 2: Try Discogs
        cover_art_data = self._fetch_cover_art_from_discogs(release_info, console)
        if cover_art_data:
            return cover_art_data
        
        # Priority 3: Try MusicBrainz if we have MBID
        mbid = release_info.mbid.strip() if release_info.mbid else ""
        
        # Check if MBID looks like a MusicBrainz UUID (has dashes)
        is_musicbrainz_mbid = mbid and '-' in mbid and len(mbid) == 36
        
        if mbid and is_musicbrainz_mbid:
            if console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetching cover art from MusicBrainz for release...[/dim]")
            cover_art_data = self.fetch_cover_art(mbid, console)
            if cover_art_data:
                return cover_art_data
            elif console:
                console.print(f"[yellow]⚠[/yellow] Cover art not available from MusicBrainz")
        elif mbid and not is_musicbrainz_mbid:
            # This is likely a Discogs ID, not a MusicBrainz MBID
            if console:
                console.print(f"[yellow]⚠[/yellow] MBID appears to be from Discogs (not MusicBrainz). Cover art requires MusicBrainz MBID.")
        
        # Fallback 3: Try to extract cover art from existing tracks in the folder
        if folder_path and folder_path.exists():
            if console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Trying to extract cover art from existing tracks in folder...[/dim]")
            cover_art_data = self._extract_cover_art_from_folder(folder_path, console)
            if cover_art_data:
                return cover_art_data
        
        return None

