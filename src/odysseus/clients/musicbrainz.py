"""
MusicBrainz Client Module
A client for searching the MusicBrainz database for music information.
"""

import requests
import json
import time
import sys
import ssl
from pathlib import Path
from typing import Dict, List, Optional, Any
from rich.console import Console
from ..models.song import SongData
from ..models.search_results import MusicBrainzSong
from ..models.releases import Track, ReleaseInfo
from ..core.config import MUSICBRAINZ_CONFIG, ERROR_MESSAGES, DOWNLOADS_DIR
from ..utils.string_utils import normalize_string
from ..utils.cache import get_search_cache, get_release_info_cache, cache_key
from .path_utils import PathUtils
from .network_agent import NetworkAgent

console = Console()

# Constants
BASE_MAX_RETRIES = 3
RETRY_DELAY_BASE = 2
MAX_RETRIES_TRANSIENT_SSL = 5
PAGINATION_LIMIT = 100
COMPILATION_TYPES = {'Compilation'}
JOIN_PHRASES = {'&', 'and', 'And', 'AND'}


class MusicBrainzClient:
    """MusicBrainz search client."""
    
    def __init__(self):
        self.base_url = MUSICBRAINZ_CONFIG["BASE_URL"]
        self.user_agent = MUSICBRAINZ_CONFIG["USER_AGENT"]
        self.request_delay = MUSICBRAINZ_CONFIG["REQUEST_DELAY"]
        self.max_results = MUSICBRAINZ_CONFIG["MAX_RESULTS"]
        self.timeout = MUSICBRAINZ_CONFIG["TIMEOUT"]
        
        # Initialize polymorphic network agent for adaptive header management
        self.network_agent = NetworkAgent(self.user_agent)
        
        self.session = requests.Session()
        # Use network agent's current header strategy
        self.network_agent.update_session_headers(self.session)
        
        # SSL verification is enabled by default for security
        # MusicBrainz uses valid SSL certificates, so verification should work
        self.session.verify = True
        
        # Configure SSL context for better connection handling
        try:
            import urllib3
            # Disable SSL warnings if we're handling them explicitly
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except ImportError:
            pass
        
        # Configure session with retry strategy and connection pooling
        try:
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # Create a custom SSL context
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = True
            ssl_context.verify_mode = ssl.CERT_REQUIRED
            
            # Custom HTTPAdapter with better connection management
            class CustomHTTPAdapter(HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    # Add SSL context to kwargs (maxsize and block are already handled by positional args)
                    kwargs['ssl_context'] = ssl_context
                    return super().init_poolmanager(*args, **kwargs)
            
            retry_strategy = Retry(
                total=2,  # Reduced from 3 to avoid compounding with our manual retries
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET", "HEAD"],
                respect_retry_after_header=True
            )
            adapter = CustomHTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=3,  # Reduced from 10 to avoid stale connections
                pool_maxsize=5  # Reduced from 10
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
        except ImportError:
            # urllib3 might not be available, continue without retry strategy
            pass
        
        # Track if we should try HTTP fallback (only as last resort)
        self.use_http_fallback = False
        
        # Initialize path utils for checking existing releases
        self.path_utils = PathUtils()
    
    def _refresh_connection_pool(self, use_network_agent: bool = True):
        """
        Refresh the connection pool to avoid stale connections that cause SSL errors.
        This closes existing connections and forces new ones to be created.
        
        Args:
            use_network_agent: If True, use the network agent's current header strategy
        """
        try:
            # Close all existing connections in the pool
            self.session.close()
            # Create a new session with fresh connections
            self.session = requests.Session()
            
            # Use network agent headers if enabled, otherwise use default
            if use_network_agent:
                self.network_agent.update_session_headers(self.session)
            else:
                self.session.headers.update({
                    'User-Agent': self.user_agent,
                    'Accept': 'application/json',
                    'Connection': 'close'
                })
            
            self.session.verify = True
            
            # Re-mount adapters
            try:
                from requests.adapters import HTTPAdapter
                from urllib3.util.retry import Retry
                
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = True
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                
                class CustomHTTPAdapter(HTTPAdapter):
                    def init_poolmanager(self, *args, **kwargs):
                        # Add SSL context to kwargs (maxsize and block are already handled by positional args)
                        kwargs['ssl_context'] = ssl_context
                        return super().init_poolmanager(*args, **kwargs)
                
                retry_strategy = Retry(
                    total=2,
                    backoff_factor=0.5,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["GET", "HEAD"],
                    respect_retry_after_header=True
                )
                adapter = CustomHTTPAdapter(
                    max_retries=retry_strategy,
                    pool_connections=3,
                    pool_maxsize=5
                )
                self.session.mount("http://", adapter)
                self.session.mount("https://", adapter)
            except ImportError:
                pass
        except Exception:
            # If refresh fails, continue with existing session
            pass
    
    def _log(self, message: str, batch_progress: Optional[tuple[int, int]] = None, dim: bool = False):
        """Log message with optional batch progress prefix and dimming."""
        prefix = f"[{batch_progress[0]}/{batch_progress[1]}] " if batch_progress else ""
        # Add newline at start to ensure message appears on new line (important when spinner is active)
        if dim:
            console.print(f"\n{prefix}[dim]{message}[/dim]")
        else:
            console.print(f"\n{prefix}{message}")
    
    def _check_release_folder_exists(self, song_data: SongData) -> bool:
        """
        Check if a release folder already exists for the given artist/album/year.
        
        Args:
            song_data: Song information with artist, album, and optional release_year
            
        Returns:
            True if folder exists and contains audio files, False otherwise
        """
        try:
            # Create metadata dict similar to what PathUtils.create_organized_path expects
            metadata = {
                'artist': song_data.artist or 'Unknown Artist',
                'album': song_data.album or 'Unknown Album',
                'year': song_data.release_year,
                'title': song_data.album or 'Unknown Album'
            }
            
            # Get the expected folder path
            expected_folder = self.path_utils.create_organized_path(DOWNLOADS_DIR, metadata)
            
            # Check if folder exists
            if not expected_folder.exists():
                return False
            
            # Check if folder contains audio files
            audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
            system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
            
            for ext in audio_extensions:
                audio_files = list(expected_folder.glob(f"*{ext}"))
                audio_files = [f for f in audio_files if f.is_file() and f.name not in system_files]
                if audio_files:
                    return True
            
            return False
        except Exception:
            # If any error occurs during checking, assume folder doesn't exist
            return False
    
    def _build_query(self, **kwargs) -> str:
        """Build MusicBrainz query string from keyword arguments."""
        query_parts = []
        if kwargs.get('title'):
            query_parts.append(f'title:"{kwargs["title"]}"')
        if kwargs.get('artist'):
            query_parts.append(f'artist:"{kwargs["artist"]}"')
        if kwargs.get('album'):
            query_parts.append(f'release:"{kwargs["album"]}"')
        if kwargs.get('release'):
            query_parts.append(f'title:"{kwargs["release"]}"')
        if kwargs.get('date'):
            query_parts.append(f'date:{kwargs["date"]}')
        if kwargs.get('release_type'):
            query_parts.append(f'type:"{kwargs["release_type"]}"')
        return ' AND '.join(query_parts)
    
    def _make_request(self, url: str, params: Dict[str, Any], batch_progress: Optional[tuple[int, int]] = None, reduced_retries: bool = False) -> Optional[Dict[str, Any]]:
        """
        Make a request with SSL error handling and retries.
        
        Args:
            url: Request URL
            params: Request parameters
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
            reduced_retries: If True, reduce retry attempts for faster failure (useful when release already exists)
        """
        retry_delay = RETRY_DELAY_BASE
        seen_transient_ssl_error = False
        max_retries = BASE_MAX_RETRIES if not reduced_retries else 2  # Reduce to 2 retries if release exists
        
        # Track current strategy to detect when it changes
        current_strategy_name = self.network_agent.get_current_strategy_name()
        
        # Calculate page info
        page_info = ""
        if 'offset' in params and 'limit' in params:
            offset, limit = params.get('offset', 0), params.get('limit', PAGINATION_LIMIT)
            if limit > 0:
                page_info = f" (page {(offset // limit) + 1})"
        
        attempt = 0
        strategy_attempt = 0  # Attempts with current strategy
        while attempt < max_retries:
            try:
                self._log(f"Making request to MusicBrainz{page_info} (attempt {attempt + 1}/{max_retries})", batch_progress, dim=True)
                # Use stream=False and explicitly close connection to avoid reuse issues
                response = self.session.get(url, params=params, timeout=self.timeout, stream=False)
                
                # Check for rate limiting (429) before raising for status
                # MusicBrainz limits to 1 request per second - they may drop connections if exceeded
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = 60  # Default to 60 seconds if Retry-After is invalid
                    else:
                        # No Retry-After header, wait at least 60 seconds to respect rate limit
                        wait_time = 60
                    
                    self._log(f"Rate limit exceeded (429). MusicBrainz allows 1 request/second. Waiting {wait_time} seconds...", batch_progress)
                    time.sleep(wait_time)
                    # Don't count rate limit as a failed attempt, retry immediately
                    continue
                
                response.raise_for_status()
                result = response.json()
                response.close()  # Explicitly close connection
                time.sleep(self.request_delay)
                return result
                
            except requests.exceptions.HTTPError as e:
                # Handle HTTP errors (including 429 if raise_for_status was called)
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    if status_code == 429:
                        retry_after = e.response.headers.get('Retry-After')
                        if retry_after:
                            try:
                                wait_time = int(retry_after)
                            except ValueError:
                                wait_time = 60
                        else:
                            wait_time = 60
                        
                        self._log(f"Rate limit exceeded (429). MusicBrainz allows 1 request/second. Waiting {wait_time} seconds...", batch_progress)
                        time.sleep(wait_time)
                        if attempt < max_retries - 1:
                            continue
                        else:
                            self._log("Max retries reached after rate limit. Aborting.", batch_progress)
                            return None
                
                # Other HTTP errors
                self._log(f"HTTP Error (attempt {attempt + 1}): {e}", batch_progress, dim=True)
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    attempt += 1
                    continue
                else:
                    return None
                
            except requests.exceptions.SSLError as e:
                error_str = str(e).lower()
                is_transient = any(x in error_str for x in ['eof', 'unexpected_eof', 'connection'])
                
                if is_transient and not seen_transient_ssl_error:
                    seen_transient_ssl_error = True
                    # If reduced_retries is True, use fewer retries even for transient errors
                    max_retries = 2 if reduced_retries else MAX_RETRIES_TRANSIENT_SSL
                
                # Check if strategy has changed (to reset strategy_attempt counter)
                new_strategy_name = self.network_agent.get_current_strategy_name()
                strategy_changed = new_strategy_name != current_strategy_name
                if strategy_changed:
                    current_strategy_name = new_strategy_name
                    strategy_attempt = 0  # Reset counter for new strategy
                    retry_delay = RETRY_DELAY_BASE  # Reset retry delay for new strategy
                
                # For transient SSL errors, try switching header strategies after 2 attempts with current strategy
                # This gives each strategy a fair chance before switching
                should_switch_strategy = is_transient and strategy_attempt >= 2
                strategy_switched_this_iteration = False
                
                if should_switch_strategy:
                    # Try switching strategy after giving current strategy a fair chance
                    self._log(f"Transient SSL error persists after {strategy_attempt} attempts with strategy: {current_strategy_name}", batch_progress, dim=True)
                    
                    switched = self.network_agent.switch_to_next_strategy(e)
                    if switched:
                        new_strategy = self.network_agent.get_current_strategy_name()
                        self._log(f"Switching to header strategy: {new_strategy} to address SSL connection issues", batch_progress)
                        current_strategy_name = new_strategy
                        strategy_attempt = 0  # Reset counter for new strategy
                        retry_delay = RETRY_DELAY_BASE  # Reset retry delay
                        strategy_switched_this_iteration = True
                    else:
                        # Reset to default if all strategies exhausted
                        self._log("All header strategies exhausted, resetting to default", batch_progress)
                        self.network_agent.reset_to_default()
                        current_strategy_name = self.network_agent.get_current_strategy_name()
                        strategy_attempt = 0
                        retry_delay = RETRY_DELAY_BASE
                        strategy_switched_this_iteration = True
                
                # Always refresh connection pool on SSL errors to avoid stale connections
                # This helps prevent SSL EOF errors caused by connection reuse issues
                self._refresh_connection_pool(use_network_agent=True)
                
                error_msg = "SSL Connection Error" if is_transient else "SSL Error"
                strategy_info = f" (strategy: {current_strategy_name}, attempt {strategy_attempt + 1})" if is_transient else ""
                self._log(f"{error_msg} (attempt {attempt + 1}/{max_retries}){strategy_info}: {e}", batch_progress, dim=True)
                if is_transient:
                    self._log("This may be a transient network issue or rate limiting. MusicBrainz limits to 1 request/second.", batch_progress)
                    self._log("Refreshing connection and waiting before retrying...", batch_progress)
                else:
                    self._log("Note: SSL verification is required for security. Please check your system's SSL certificates.", batch_progress)
                
                if attempt < max_retries - 1:
                    # For transient SSL errors (especially EOF), wait longer to respect rate limits
                    # MusicBrainz may drop connections when rate limits are exceeded
                    # If we just switched strategies, use base delay for first attempt with new strategy
                    if is_transient:
                        if strategy_switched_this_iteration or strategy_changed:
                            # First attempt with new strategy - use base delay
                            delay = max(RETRY_DELAY_BASE, 2.0)
                        else:
                            # Continue with exponential backoff
                            delay = max(retry_delay * 2, 2.0)
                    else:
                        delay = retry_delay
                    self._log(f"Retrying in {delay} seconds...", batch_progress)
                    time.sleep(delay)
                    # Only double retry_delay if we didn't switch strategies (to avoid compounding delays)
                    if not strategy_switched_this_iteration and not strategy_changed:
                        retry_delay *= 2
                    else:
                        # Reset to base delay after strategy switch
                        retry_delay = RETRY_DELAY_BASE
                    attempt += 1
                    # Only increment strategy_attempt if we didn't switch strategies this iteration
                    if not strategy_switched_this_iteration and not strategy_changed:
                        strategy_attempt += 1
                    continue
                else:
                    final_msg = (f"SSL connection failed after {max_retries} attempts. This may be a network issue." 
                               if is_transient else "SSL verification failed. Please check your system's SSL certificates.")
                    self._log(final_msg, batch_progress)
                    return None
                    
            except requests.exceptions.ConnectionError as e:
                self._log(f"Connection Error (attempt {attempt + 1}): {e}", batch_progress, dim=True)
                
                # Check if strategy has changed (to reset strategy_attempt counter)
                new_strategy_name = self.network_agent.get_current_strategy_name()
                strategy_changed = new_strategy_name != current_strategy_name
                if strategy_changed:
                    current_strategy_name = new_strategy_name
                    strategy_attempt = 0  # Reset counter for new strategy
                    retry_delay = RETRY_DELAY_BASE  # Reset retry delay for new strategy
                
                # Check if this is the specific ProtocolError with Invalid argument
                should_switch = self.network_agent.should_switch_strategy(e)
                strategy_switched_this_iteration = False
                
                if should_switch:
                    self._log(f"Detected ProtocolError with Invalid argument. Current strategy: {current_strategy_name}", batch_progress)
                    
                    # Switch to next header strategy immediately for ProtocolError
                    switched = self.network_agent.switch_to_next_strategy(e)
                    if switched:
                        new_strategy = self.network_agent.get_current_strategy_name()
                        self._log(f"Switching to header strategy: {new_strategy}", batch_progress)
                        current_strategy_name = new_strategy
                        strategy_attempt = 0  # Reset counter for new strategy
                        retry_delay = RETRY_DELAY_BASE  # Reset retry delay
                        strategy_switched_this_iteration = True
                        # Refresh connection pool with new headers
                        self._refresh_connection_pool(use_network_agent=True)
                    else:
                        self._log("All header strategies exhausted, resetting to default", batch_progress)
                        self.network_agent.reset_to_default()
                        current_strategy_name = self.network_agent.get_current_strategy_name()
                        strategy_attempt = 0
                        retry_delay = RETRY_DELAY_BASE
                        strategy_switched_this_iteration = True
                        self._refresh_connection_pool(use_network_agent=True)
                else:
                    self._log("This may indicate rate limiting. MusicBrainz limits to 1 request/second.", batch_progress)
                    # Refresh connection pool on connection errors too
                    self._refresh_connection_pool(use_network_agent=True)
                
                if attempt < max_retries - 1:
                    # Wait at least 2 seconds to respect rate limits
                    # If we just switched strategies, use base delay for first attempt with new strategy
                    if strategy_switched_this_iteration or strategy_changed:
                        delay = max(RETRY_DELAY_BASE, 2.0)
                    else:
                        delay = max(retry_delay, 2.0)
                    self._log(f"Retrying in {delay} seconds...", batch_progress)
                    time.sleep(delay)
                    # Only double retry_delay if we didn't switch strategies (to avoid compounding delays)
                    if not strategy_switched_this_iteration and not strategy_changed:
                        retry_delay *= 2
                    else:
                        # Reset to base delay after strategy switch
                        retry_delay = RETRY_DELAY_BASE
                    attempt += 1
                    # Only increment strategy_attempt if we didn't switch strategies this iteration
                    if not strategy_switched_this_iteration and not strategy_changed:
                        strategy_attempt += 1
                    continue
                else:
                    self._log("All connection retry attempts failed, trying HTTP fallback...", batch_progress)
                    return self._try_http_fallback(url, params, batch_progress)
                    
            except requests.exceptions.RequestException as e:
                self._log(f"Request Error: {e}", batch_progress, dim=True)
                return None
                
        return None
    
    def _try_http_fallback(self, url: str, params: Dict[str, Any], batch_progress: Optional[tuple[int, int]] = None) -> Optional[Dict[str, Any]]:
        """
        Try HTTP fallback if HTTPS fails (only for connection errors, not SSL errors).
        
        WARNING: HTTP is insecure and should only be used as a last resort.
        This method is kept for backward compatibility but should rarely be needed.
        """
        if self.use_http_fallback:
            return None
            
        try:
            http_url = url.replace('https://', 'http://')
            self._log(f"Warning: Trying insecure HTTP fallback: {http_url}", batch_progress)
            self._log("Note: HTTP is not secure. This should only be used if HTTPS is unavailable.", batch_progress)
            
            response = self.session.get(http_url, params=params, timeout=self.timeout, verify=False)
            response.raise_for_status()
            time.sleep(self.request_delay)
            self.use_http_fallback = True
            return response.json()
            
        except Exception as e:
            self._log(f"HTTP fallback also failed: {e}", batch_progress, dim=True)
            return None
    
    def search_recording(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None) -> List[MusicBrainzSong]:
        """
        Search for recordings in MusicBrainz.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            
        Returns:
            List of MusicBrainz results
        """
        query = self._build_query(
            title=song_data.title,
            artist=song_data.artist,
            album=song_data.album,
            date=song_data.release_year
        )
        
        url = f"{self.base_url}/recording"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': limit or self.max_results,
            'offset': offset,
            'inc': 'releases+release-groups'
        }
        
        try:
            print(f"Searching MusicBrainz recordings with query: {query}")
            data = self._make_request(url, params)
            return self._parse_recording_results(data) if data else []
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def search_release(self, song_data: SongData, offset: int = 0, limit: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """
        Search for releases (albums) in MusicBrainz with caching.
        
        Args:
            song_data: Song information to search for
            offset: Offset for pagination (default: 0)
            limit: Maximum number of results (default: uses self.max_results)
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            
        Returns:
            List of MusicBrainz results
        """
        # Generate cache key from search parameters
        cache = get_search_cache()
        key = cache_key(
            "search_release",
            song_data.album,
            song_data.artist,
            song_data.release_year,
            offset,
            limit or self.max_results,
            release_type
        )
        
        # Check cache first
        cached_result = cache.get(key)
        if cached_result is not None:
            print(f"Using cached result for: {song_data.album} by {song_data.artist}")
            return cached_result
        
        query = self._build_query(
            release=song_data.album,
            artist=song_data.artist,
            date=song_data.release_year,
            release_type=release_type
        )
        
        url = f"{self.base_url}/release"
        params = {
            'query': query,
            'fmt': 'json',
            'limit': limit or self.max_results,
            'offset': offset,
            'inc': 'release-groups'
        }
        
        try:
            # Check if release folder already exists - if so, use reduced retries for faster failure
            release_exists = self._check_release_folder_exists(song_data)
            reduced_retries = release_exists
            
            if release_exists:
                print(f"Release folder already exists for: {song_data.album} by {song_data.artist}. Using faster failure mode for connection errors.")
            
            print(f"Searching MusicBrainz releases with query: {query}")
            data = self._make_request(url, params, reduced_retries=reduced_retries)
            results = self._parse_release_results(data) if data else []
            
            # Cache the results
            cache.set(key, results)
            
            return results
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return []
    
    def get_release_info(self, release_mbid: str, batch_progress: Optional[tuple[int, int]] = None) -> Optional[ReleaseInfo]:
        """
        Get detailed release information including track listing with caching.
        
        Args:
            release_mbid: MusicBrainz release ID
            batch_progress: Optional tuple (current, total) for batch operations (e.g., (1, 5))
            
        Returns:
            ReleaseInfo with tracks or None if failed
        """
        # Generate cache key
        cache = get_release_info_cache()
        key = cache_key("get_release_info", release_mbid)
        
        # Check cache first (skip cache check for batch operations to show progress)
        if not batch_progress:
            cached_result = cache.get(key)
            if cached_result is not None:
                print(f"Using cached release info for MBID: {release_mbid}")
                return cached_result
        
        url = f"{self.base_url}/release/{release_mbid}"
        params = {
            'inc': 'recordings+artist-credits+media+release-groups',
            'fmt': 'json'
        }
        
        try:
            if not batch_progress:
                print(f"Fetching release details for MBID: {release_mbid}")
            data = self._make_request(url, params, batch_progress=batch_progress)
            result = self._parse_release_info(data) if data else None
            
            # Cache the result (even for batch operations, cache after fetching)
            if result is not None:
                cache.set(key, result)
            
            return result
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return None
    
    def search_artist_releases(self, artist: str, year: Optional[int] = None, max_results: Optional[int] = None, release_type: Optional[str] = None) -> List[MusicBrainzSong]:
        """
        Search for releases by a specific artist.
        Fetches all available releases using pagination.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            max_results: Optional maximum number of results to fetch (None = fetch all)
            release_type: Optional release type filter (e.g., "Album", "Single", "EP", "Compilation", "Live", etc.)
            
        Returns:
            List of releases by the artist
        """
        query = self._build_query(artist=artist, date=year, release_type=release_type)
        url = f"{self.base_url}/release"
        all_results = []
        offset = 0
        
        try:
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': PAGINATION_LIMIT,
                    'offset': offset,
                    'inc': 'release-groups'
                }
                
                data = self._make_request(url, params)
                if not data:
                    break
                
                releases = data.get('releases', [])
                if not releases:
                    break
                
                all_results.extend(self._parse_release_results(data))
                
                count = data.get('count', 0)
                if offset + len(releases) >= count:
                    break
                
                if max_results and len(all_results) >= max_results:
                    all_results = all_results[:max_results]
                    break
                
                offset += PAGINATION_LIMIT
                time.sleep(self.request_delay)
            
            return all_results
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []
    
    def search_artist_compilations(self, artist: str, year: Optional[int] = None, max_results: Optional[int] = None) -> List[MusicBrainzSong]:
        """
        Search for compilations where the artist appears as a track artist but not as the main release artist.
        This finds compilations, soundtracks, and other multi-artist releases where the artist contributed tracks.
        
        Args:
            artist: Artist name to search for
            year: Optional year filter
            max_results: Optional maximum number of results to fetch (None = fetch all)
            
        Returns:
            List of compilation releases where the artist appears
        """
        query = self._build_query(artist=artist, date=year)
        url = f"{self.base_url}/recording"
        all_results = []
        seen_release_mbids = set()
        offset = 0
        
        try:
            while True:
                params = {
                    'query': query,
                    'fmt': 'json',
                    'limit': PAGINATION_LIMIT,
                    'offset': offset,
                    'inc': 'releases+release-groups'
                }
                
                data = self._make_request(url, params)
                if not data:
                    break
                
                recordings = data.get('recordings', [])
                if not recordings:
                    break
                
                for recording in recordings:
                    artist_credits = recording.get('artist-credit', [])
                    recording_artist = artist_credits[0].get('name', '') if artist_credits else ''
                    
                    for release in recording.get('releases', []):
                        release_mbid = release.get('id', '')
                        if not release_mbid or release_mbid in seen_release_mbids:
                            continue
                        
                        release_artist_credits = release.get('artist-credit', [])
                        release_artist = release_artist_credits[0].get('name', '') if release_artist_credits else ''
                        
                        release_group = release.get('release-group', {})
                        release_type = release_group.get('primary-type')
                        secondary_types = release_group.get('secondary-types', [])
                        
                        is_compilation = (
                            release_type in COMPILATION_TYPES or
                            any(t in COMPILATION_TYPES for t in secondary_types)
                        )
                        
                        normalized_recording = normalize_string(recording_artist)
                        normalized_release = normalize_string(release_artist)
                        normalized_search = normalize_string(artist)
                        
                        if (is_compilation and 
                            normalized_recording == normalized_search and
                            normalized_release != normalized_recording):
                            
                            album = release.get('title', '')
                            release_date = release.get('date', '')
                            original_release_date = release_group.get('first-release-date')
                            
                            if not release_date and original_release_date:
                                release_date = original_release_date
                            
                            if year:
                                try:
                                    release_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None
                                    if release_year != year:
                                        continue
                                except ValueError:
                                    pass
                            
                            result = MusicBrainzSong(
                                title='',
                                artist=release_artist,
                                album=album,
                                release_date=release_date,
                                original_release_date=original_release_date,
                                genre=None,
                                release_type='Compilation' if release_type == 'Compilation' or 'Compilation' in secondary_types else release_type,
                                mbid=release_mbid,
                                score=recording.get('score', 0),
                                url=f"https://musicbrainz.org/release/{release_mbid}"
                            )
                            
                            all_results.append(result)
                            seen_release_mbids.add(release_mbid)
                            
                            if max_results and len(all_results) >= max_results:
                                return all_results[:max_results]
                
                count = data.get('count', 0)
                if offset + len(recordings) >= count or (max_results and len(all_results) >= max_results):
                    break
                
                offset += PAGINATION_LIMIT
                time.sleep(self.request_delay)
            
            return all_results
        except Exception as e:
            print(f"{ERROR_MESSAGES['NETWORK_ERROR']}: {e}")
            return all_results if all_results else []
    
    def _parse_recording_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse recording search results."""
        results = []
        
        for recording in data.get('recordings', []):
            title = recording.get('title', '')
            mbid = recording.get('id', '')
            score = recording.get('score', 0)
            
            artist_credits = recording.get('artist-credit', [])
            artist = artist_credits[0].get('name', '') if artist_credits else ''
            
            album = None
            release_date = None
            original_release_date = None
            genre = None
            
            releases = recording.get('releases', [])
            if releases:
                release = releases[0]
                album = release.get('title', '')
                release_date = release.get('date', '')
                
                release_group = release.get('release-group')
                if release_group:
                    original_release_date = release_group.get('first-release-date')
                    if not release_date and original_release_date:
                        release_date = original_release_date
                
                genres = release.get('genres', [])
                genre = genres[0] if genres else None
            
            results.append(MusicBrainzSong(
                title=title,
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=genre,
                mbid=mbid,
                score=score,
                url=f"https://musicbrainz.org/recording/{mbid}"
            ))
        
        return results
    
    def _parse_release_results(self, data: Dict[str, Any]) -> List[MusicBrainzSong]:
        """Parse release search results."""
        results = []
        
        for release in data.get('releases', []):
            album = release.get('title', '')
            mbid = release.get('id', '')
            score = release.get('score', 0)
            release_date = release.get('date', '')
            
            artist = self._parse_artist_credit(release.get('artist-credit', []))
            
            release_type = None
            original_release_date = None
            release_group = release.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    release_type = secondary_types[0]
                original_release_date = release_group.get('first-release-date')
                if not release_date and original_release_date:
                    release_date = original_release_date
            
            results.append(MusicBrainzSong(
                title='',
                artist=artist,
                album=album,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=None,
                release_type=release_type,
                mbid=mbid,
                score=score,
                url=f"https://musicbrainz.org/release/{mbid}"
            ))
        
        return results
    
    def _parse_artist_credit(self, artist_credits: List[Dict[str, Any]]) -> str:
        """
        Parse MusicBrainz artist-credit array to build full artist name.
        
        Handles collaborative artists with join phrases (e.g., "Artist A & Artist B").
        """
        if not artist_credits:
            return ''
        
        artist_names = []
        join_phrases = []
        artist_parts = []
        
        for credit in artist_credits:
            if 'artist' in credit:
                artist_obj = credit['artist']
                name = artist_obj.get('name') if isinstance(artist_obj, dict) else artist_obj
                if name:
                    artist_names.append(name)
                    artist_parts.append(name)
            elif 'name' in credit:
                name = credit['name']
                name_stripped = name.strip()
                is_join_phrase = (
                    not name_stripped or
                    name_stripped in JOIN_PHRASES or
                    '&' in name_stripped or
                    (len(name_stripped) <= 5 and not any(c.isalnum() for c in name_stripped))
                )
                
                if is_join_phrase:
                    normalized = ' & ' if name_stripped in JOIN_PHRASES else name
                    join_phrases.append(normalized)
                    artist_parts.append(normalized)
                else:
                    artist_names.append(name)
                    artist_parts.append(name)
        
        return ' & '.join(artist_names) if len(artist_names) > 1 and not join_phrases else ''.join(artist_parts)
    
    def _parse_release_info(self, data: Dict[str, Any]) -> Optional[ReleaseInfo]:
        """Parse detailed release information."""
        try:
            title = data.get('title', '')
            mbid = data.get('id', '')
            release_date = data.get('date', '')
            
            artist = self._parse_artist_credit(data.get('artist-credit', []))
            
            genres = data.get('genres', [])
            genre = genres[0].get('name', '') if genres else None
            
            release_type = None
            original_release_date = None
            release_group = data.get('release-group')
            if release_group:
                release_type = release_group.get('primary-type')
                secondary_types = release_group.get('secondary-types', [])
                if secondary_types:
                    release_type = secondary_types[0]
                original_release_date = release_group.get('first-release-date')
                if not release_date and original_release_date:
                    release_date = original_release_date
            
            # Parse tracks
            tracks = []
            current_position = 1
            
            for medium in data.get('media', []):
                for track_data in medium.get('tracks', []):
                    recording = track_data.get('recording', {})
                    track_title = recording.get('title', '')
                    track_mbid = recording.get('id', '')
                    
                    track_artist_credits = recording.get('artist-credit', [])
                    track_artist = self._parse_artist_credit(track_artist_credits) or artist
                    
                    duration = None
                    for source in [track_data, recording]:
                        if 'length' in source and source['length']:
                            duration = self._format_duration(source['length'])
                            break
                    
                    tracks.append(Track(
                        position=current_position,
                        title=track_title,
                        artist=track_artist,
                        duration=duration,
                        mbid=track_mbid
                    ))
                    current_position += 1
            
            return ReleaseInfo(
                title=title,
                artist=artist,
                release_date=release_date,
                original_release_date=original_release_date,
                genre=genre,
                release_type=release_type,
                mbid=mbid,
                url=f"https://musicbrainz.org/release/{mbid}",
                tracks=tracks
            )
            
        except Exception as e:
            print(f"Error parsing release info: {e}")
            return None
    
    def _format_duration(self, duration_value: int) -> str:
        """
        Format duration to MM:SS format.
        MusicBrainz API 'length' field is in milliseconds.
        """
        if not duration_value:
            return None
        
        # MusicBrainz 'length' field is in milliseconds
        # Convert to seconds (round to nearest second for display)
        seconds = round(duration_value / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        
        return f"{minutes:02d}:{seconds:02d}"
