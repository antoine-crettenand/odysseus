"""
Cover art fetching service for retrieving cover art from various sources.
"""

import requests
from typing import Optional
from pathlib import Path
from ....models.releases import ReleaseInfo
from ....core.http.network_agent import NetworkAgent
from ....core.cache import MemoryCache
from ....core.http.http_client import HttpClient
from ...music.common.date_utils import get_original_release_year
from ...music.identity import select_best_release_match


class CoverArtFetcher:
    """Service for fetching cover art from various sources."""

    @staticmethod
    def _is_image_payload(data: Optional[bytes]) -> bool:
        """Return whether bytes look like a supported image payload."""
        if not data or len(data) < 12:
            return False
        if data.startswith(b"\xff\xd8\xff"):
            return True
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return True
        if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
            return True
        # WebP: RIFF....WEBP
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return True
        return False

    def __init__(
        self,
        network_agent=None,
        cache_manager=None,
        http_client=None,
        musicbrainz_client=None,
        discogs_client=None,
        spotify_client=None,
    ):
        """
        Initialize cover art fetcher with dependencies.

        Args:
            network_agent: Optional NetworkAgent instance
            cache_manager: Optional CacheManager instance
            http_client: Shared HTTP client
            musicbrainz_client: Shared MusicBrainz provider
            discogs_client: Shared Discogs provider
            spotify_client: Shared Spotify provider
        """
        # Use the same cache protocol for managed and local caches.
        if cache_manager:
            self.cover_art_cache = cache_manager.get_cache("cover_art")
            self.discogs_cache = cache_manager.get_cache(
                "discogs_search",
                backend="memory",
            )
        else:
            self.cover_art_cache = MemoryCache()
            self.discogs_cache = MemoryCache()

        # Initialize network agent and HTTP client
        if network_agent is None:
            from ....core.config import PROJECT_NAME, PROJECT_VERSION
            self.network_agent = NetworkAgent(
                f"{PROJECT_NAME}/{PROJECT_VERSION} "
                "(https://github.com/antoine-crettenand/odysseus)"
            )
        else:
            self.network_agent = network_agent
        self.http_client = http_client or HttpClient(
            network_agent=self.network_agent,
            default_timeout=10,
        )
        self.musicbrainz_client = musicbrainz_client
        self.discogs_client = discogs_client
        self.spotify_client = spotify_client

    def _handle_fetch_error(
        self,
        cache_key: str,
        error_msg: str,
        console=None,
        use_cache: bool = True,
        cache_negative: bool = False,
    ):
        """Handle fetch error by logging; optionally cache a negative result."""
        if console:
            console.print(f"[yellow]⚠[/yellow] {error_msg}")
        # Only cache definitive absences (e.g. HTTP 404), not transient failures
        if use_cache and cache_negative:
            self.cover_art_cache.set(cache_key, None)

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
        if use_cache and self.cover_art_cache.has(url):
            cached_data = self.cover_art_cache.get(url)
            if cached_data is None:
                return None
            if self._is_image_payload(cached_data):
                if console:
                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Using cached cover art from URL ({len(cached_data)} bytes)[/dim]")
                return cached_data
            # Stale non-image payload — fall through and refetch.

        try:
            response = self.http_client.get(
                url,
                timeout=10,
                max_retries=3,
                accepted_status_codes=(404,),
            )
            if response is None:
                self._handle_fetch_error(
                    url,
                    "Failed to fetch cover art from URL after retries",
                    console,
                    use_cache,
                    cache_negative=False,
                )
                return None

            if response.status_code == 200:
                if not self._is_image_payload(response.content):
                    self._handle_fetch_error(
                        url,
                        "Cover art URL returned a non-image payload",
                        console,
                        use_cache,
                        cache_negative=False,
                    )
                    return None
                if console:
                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetched cover art from URL ({len(response.content)} bytes)[/dim]")
                if use_cache:
                    self.cover_art_cache.set(url, response.content)
                return response.content
            if response.status_code == 404:
                self._handle_fetch_error(
                    url,
                    "Cover art URL returned 404",
                    console,
                    use_cache,
                    cache_negative=True,
                )
            else:
                self._handle_fetch_error(
                    url,
                    f"Failed to fetch cover art from URL: HTTP {response.status_code}",
                    console,
                    use_cache,
                    cache_negative=False,
                )
        except Exception as e:
            self._handle_fetch_error(
                url,
                f"Error fetching cover art from URL: {e}",
                console,
                use_cache,
                cache_negative=False,
            )

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
                console.print("[yellow]⚠[/yellow] No MBID provided for cover art fetch")
            return None

        # Check cache first
        cache_key = f"mbid:{mbid}"
        if use_cache and self.cover_art_cache.has(cache_key):
            cached_data = self.cover_art_cache.get(cache_key)
            if cached_data is not None and console:
                console.print(f"[dim blue]ℹ[/dim blue] [dim]Using cached cover art from MusicBrainz ({len(cached_data)} bytes)[/dim]")
            return cached_data

        try:
            cover_art_url = f"https://coverartarchive.org/release/{mbid}"
            response = self.http_client.get(
                cover_art_url,
                timeout=10,
                max_retries=3,
                accepted_status_codes=(404,),
            )
            if response is None:
                # Transient failure — do not negative-cache
                return None

            if response.status_code == 200:
                data = response.json()
                images = data.get('images', [])

                if not images:
                    self._handle_fetch_error(
                        cache_key,
                        f"No images found in Cover Art Archive for MBID: {mbid}",
                        console,
                        use_cache,
                        cache_negative=True,
                    )
                    return None

                # Look for front cover first, then use first image
                for image in images:
                    if image.get('front', False) or (not any(img.get('front') for img in images) and image == images[0]):
                        image_url = image.get('image')
                        if image_url:
                            img_response = self.http_client.get(image_url, timeout=10, max_retries=3)
                            if img_response and img_response.status_code == 200:
                                if not self._is_image_payload(img_response.content):
                                    continue
                                if console:
                                    prefix = "front" if image.get('front') else "first available"
                                    console.print(f"[dim blue]ℹ[/dim blue] [dim]Fetched {prefix} cover art ({len(img_response.content)} bytes)[/dim]")
                                if use_cache:
                                    self.cover_art_cache.set(cache_key, img_response.content)
                                return img_response.content
            elif response.status_code == 404:
                self._handle_fetch_error(
                    cache_key,
                    f"Cover art not found in archive for MBID: {mbid}",
                    console,
                    use_cache,
                    cache_negative=True,
                )
            else:
                self._handle_fetch_error(
                    cache_key,
                    f"Cover Art Archive returned status {response.status_code} for MBID: {mbid}",
                    console,
                    use_cache,
                    cache_negative=False,
                )
        except requests.exceptions.RequestException as e:
            self._handle_fetch_error(
                cache_key,
                f"Network error fetching cover art: {e}",
                console,
                use_cache,
                cache_negative=False,
            )
        except Exception as e:
            self._handle_fetch_error(
                cache_key,
                f"Error fetching cover art: {e}",
                console,
                use_cache,
                cache_negative=False,
            )
        return None


    def _find_musicbrainz_mbid(self, release_info: ReleaseInfo, console=None) -> Optional[str]:
        """
        Search MusicBrainz for a matching release to get MBID.

        Args:
            release_info: ReleaseInfo object with artist and title
            console: Optional console for output

        Returns:
            MusicBrainz MBID if found, None otherwise
        """
        if not release_info.artist or not release_info.title:
            return None

        try:
            from ....models.song import SongData

            release_year = get_original_release_year(release_info)

            song_data = SongData(
                title="",  # Not needed for release search
                artist=release_info.artist,
                album=release_info.title,
                release_year=release_year
            )

            musicbrainz_client = self.musicbrainz_client
            if musicbrainz_client is None:
                return None
            results = musicbrainz_client.search_release(song_data, limit=3)

            match = select_best_release_match(
                results,
                expected_album=release_info.title,
                expected_artist=release_info.artist,
                expected_year=release_year,
            )
            if match:
                return match.mbid
        except Exception as e:
            if console:
                console.print(f"[dim yellow]⚠[/dim yellow] [dim]Error searching MusicBrainz for MBID: {e}[/dim]")

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
            from ....models.song import SongData

            # Create cache key from artist and album
            artist = (release_info.artist or "").lower().strip()
            album = (release_info.title or "").lower().strip()
            cache_key = f"{artist}:{album}"

            # Check cache first
            cached_url = self.discogs_cache.get(cache_key)
            if cached_url is not None:
                if cached_url == "":  # Empty string means "not found"
                    return None
                if console:
                    console.print("[dim blue]ℹ[/dim blue] [dim]Using cached Discogs cover art URL[/dim]")
                cover_art_data = self.fetch_cover_art_from_url(cached_url, console)
                if cover_art_data:
                    if console:
                        console.print(f"[green]✓ Got cover art from Discogs ({len(cover_art_data)} bytes)[/green]")
                    return cover_art_data
                self.discogs_cache.delete(cache_key)

            # Not in cache, need to search
            if console:
                console.print("[dim blue]ℹ[/dim blue] [dim]Trying to find cover art from Discogs...[/dim]")

            discogs_client = self.discogs_client
            if discogs_client is None:
                return None

            # Build search query
            song_data = SongData(
                title="",
                artist=release_info.artist or "",
                album=release_info.title or "",
                release_year=get_original_release_year(release_info)
            )

            # Search for releases
            discogs_results = discogs_client.search_release(song_data, limit=5)

            if not discogs_results:
                self.discogs_cache.set(cache_key, "")
                return None

            result = select_best_release_match(
                discogs_results,
                expected_album=release_info.title,
                expected_artist=release_info.artist,
                expected_year=song_data.release_year,
            )
            if result:
                cover_art_url = result.cover_art_url
                if not cover_art_url and result.discogs_id:
                    detailed_info = discogs_client.get_release_info(result.discogs_id)
                    cover_art_url = (
                        detailed_info.cover_art_url if detailed_info else None
                    )
                if cover_art_url:
                    self.discogs_cache.set(cache_key, cover_art_url)
                    cover_art_data = self.fetch_cover_art_from_url(
                        cover_art_url,
                        console,
                    )
                    if cover_art_data:
                        return cover_art_data

            self.discogs_cache.set(cache_key, "")
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
            spotify_client = self.spotify_client
            if spotify_client is None:
                return None

            # Check if Spotify client is authenticated
            if not spotify_client.access_token:
                # Spotify requires authentication, skip silently
                return None

            try:
                year = get_original_release_year(release_info)
                albums = spotify_client.search_release(
                    release_info.title,
                    release_info.artist,
                    release_year=year,
                    limit=5,
                )
                album = select_best_release_match(
                    albums,
                    expected_album=release_info.title,
                    expected_artist=release_info.artist,
                    expected_year=year,
                )
                if not album:
                    return None
                cover_art_url = album.get("cover_art_url")
                return (
                    self.fetch_cover_art_from_url(cover_art_url, console)
                    if cover_art_url
                    else None
                )

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
            # Look for formats whose embedded artwork can be decoded below.
            audio_extensions = [
                '.mp3',
                '.m4a',
                '.mp4',
                '.m4p',
                '.flac',
                '.ogg',
                '.oga',
                '.opus',
                '.wav',
            ]
            existing_files = []
            for ext in audio_extensions:
                existing_files.extend(list(folder_path.glob(f"*{ext}")))

            if not existing_files:
                if console:
                    console.print("[yellow]⚠[/yellow] No audio files found in folder to extract cover art from")
                return None

            # Try each file until we find one with cover art
            for audio_file in existing_files:
                try:
                    # Try with mutagen first (works for MP3, M4A, FLAC, OGG)
                    from mutagen.mp3 import MP3
                    from mutagen.id3 import ID3NoHeaderError
                    from mutagen.mp4 import MP4
                    from mutagen.flac import FLAC, Picture
                    from mutagen.wave import WAVE
                    from mutagen import File as MutagenFile
                    import base64

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

                    elif file_ext in {'.m4a', '.mp4', '.m4p'}:
                        try:
                            audio = MP4(str(audio_file))
                            if audio.tags and 'covr' in audio.tags:
                                cover = audio.tags['covr'][0]
                                cover_data = bytes(cover)
                                if cover_data:
                                    if console:
                                        console.print(f"[green]✓ Extracted cover art from {audio_file.name} ({len(cover_data)} bytes)[/green]")
                                    return cover_data
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

                    elif file_ext == '.wav':
                        try:
                            audio = WAVE(str(audio_file))
                            if audio.tags:
                                for key in audio.tags.keys():
                                    if key.startswith('APIC'):
                                        cover_data = audio.tags[key].data
                                        if cover_data:
                                            if console:
                                                console.print(
                                                    f"[green]✓ Extracted cover art "
                                                    f"from {audio_file.name} "
                                                    f"({len(cover_data)} bytes)[/green]"
                                                )
                                            return cover_data
                        except Exception:
                            pass

                    elif file_ext in {'.ogg', '.oga', '.opus'}:
                        try:
                            audio = MutagenFile(str(audio_file))
                            pictures = (
                                audio.tags.get('metadata_block_picture', [])
                                if audio and audio.tags
                                else []
                            )
                            if pictures:
                                picture = Picture(base64.b64decode(pictures[0]))
                                if picture.data:
                                    if console:
                                        console.print(
                                            f"[green]✓ Extracted cover art from "
                                            f"{audio_file.name} "
                                            f"({len(picture.data)} bytes)[/green]"
                                        )
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

                except Exception:
                    # Continue to next file if this one fails
                    continue

            if console:
                console.print("[yellow]⚠[/yellow] No cover art found in existing audio files")
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
        # Priority 1: Use the provider-supplied URL when available.
        if release_info.cover_art_url:
            cover_art_data = self.fetch_cover_art_from_url(
                release_info.cover_art_url,
                console,
            )
            if cover_art_data:
                return cover_art_data

        # If no Spotify URL, try searching Spotify
        if console:
            console.print("[dim blue]ℹ[/dim blue] [dim]Trying to find cover art from Spotify...[/dim]")
        cover_art_data = self._fetch_cover_art_from_spotify(release_info, console)
        if cover_art_data:
            return cover_art_data

        # Priority 2: Try MusicBrainz if we have MBID
        mbid = release_info.mbid.strip() if release_info.mbid else ""

        # Check if MBID looks like a MusicBrainz UUID (has dashes)
        is_musicbrainz_mbid = mbid and '-' in mbid and len(mbid) == 36

        if mbid and is_musicbrainz_mbid:
            if console:
                console.print("[dim blue]ℹ[/dim blue] [dim]Fetching cover art from MusicBrainz for release...[/dim]")
            cover_art_data = self.fetch_cover_art(mbid, console)
            if cover_art_data:
                return cover_art_data
            elif console:
                console.print("[yellow]⚠[/yellow] Cover art not available from MusicBrainz")

        # If MBID is a Discogs ID or we don't have a valid MusicBrainz MBID,
        # try searching MusicBrainz by artist/album to find a matching release
        if not mbid or not is_musicbrainz_mbid:
            if console:
                if mbid and not is_musicbrainz_mbid:
                    console.print("[dim blue]ℹ[/dim blue] [dim]MBID appears to be from Discogs. Searching MusicBrainz for matching release...[/dim]")
                else:
                    console.print("[dim blue]ℹ[/dim blue] [dim]Trying to find MusicBrainz release for cover art...[/dim]")
            musicbrainz_mbid = self._find_musicbrainz_mbid(release_info, console)
            if musicbrainz_mbid:
                if console:
                    console.print("[dim blue]ℹ[/dim blue] [dim]Found MusicBrainz release. Fetching cover art...[/dim]")
                cover_art_data = self.fetch_cover_art(musicbrainz_mbid, console)
                if cover_art_data:
                    return cover_art_data

        # Priority 3: Try Discogs before falling back to an existing local file.
        cover_art_data = self._fetch_cover_art_from_discogs(release_info, console)
        if cover_art_data:
            return cover_art_data

        # Priority 4: Try to extract cover art from existing tracks in the folder
        if folder_path and folder_path.exists():
            if console:
                console.print("[dim blue]ℹ[/dim blue] [dim]Trying to extract cover art from existing tracks in folder...[/dim]")
            cover_art_data = self._extract_cover_art_from_folder(folder_path, console)
            if cover_art_data:
                return cover_art_data

        return None
