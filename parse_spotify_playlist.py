#!/usr/bin/env python3
"""
Script to parse a Spotify playlist URL or user collection and write all artists and albums to a text file.
"""

import sys
import os
import argparse
import requests
import re
from typing import Set, Tuple, Optional

# Add src to path to import odysseus modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from odysseus.clients.spotify import SpotifyClient


def extract_release_year(release_date: Optional[str]) -> Optional[int]:
    """
    Extract year from Spotify release_date field.
    
    Spotify release_date can be in formats:
    - "YYYY" (e.g., "1972")
    - "YYYY-MM" (e.g., "1972-03")
    - "YYYY-MM-DD" (e.g., "1972-03-15")
    
    Returns:
        Year as integer, or None if not available
    """
    if not release_date:
        return None
    
    # Extract year (first 4 digits)
    match = re.match(r'^(\d{4})', release_date)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def get_user_collection_artists_and_albums(
    access_token: str, 
    base_url: str, 
    timeout: int,
    collection_type: str = "tracks"
) -> Set[Tuple[str, str, Optional[int]]]:
    """
    Get all unique artist-album-year tuples from a user's collection (liked songs or saved albums).
    
    Args:
        access_token: User access token with user-library-read scope
        base_url: Spotify API base URL
        timeout: Request timeout
        collection_type: "tracks" for liked songs, "albums" for saved albums
    
    Returns:
        Set of tuples (artist, album, year)
    """
    artist_albums = set()
    
    if collection_type == "tracks":
        # Get liked songs (saved tracks)
        url = f"{base_url}/me/tracks"
    elif collection_type == "albums":
        # Get saved albums
        url = f"{base_url}/me/albums"
    else:
        raise ValueError(f"Invalid collection_type: {collection_type}")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    offset = 0
    limit = 50
    
    while True:
        params = {"limit": limit, "offset": offset}
        response = requests.get(url, headers=headers, params=params, timeout=timeout)
        
        if response.status_code == 401:
            raise Exception("Invalid or expired user access token. Please get a new token.")
        elif response.status_code != 200:
            raise Exception(f"Failed to fetch collection: {response.status_code} - {response.text}")
        
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            break
        
        for item in items:
            if collection_type == "tracks":
                # For liked songs, item structure is {"track": {...}}
                track_data = item.get("track")
                if not track_data:
                    continue
                
                # Get artist name
                artists = track_data.get("artists", [])
                artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
                
                # Get album name and release date
                album_data = track_data.get("album", {})
                album_name = album_data.get("name", "Unknown Album")
                release_date = album_data.get("release_date")
                release_year = extract_release_year(release_date)
                
            elif collection_type == "albums":
                # For saved albums, item structure is {"album": {...}}
                album_data = item.get("album")
                if not album_data:
                    continue
                
                album_name = album_data.get("name", "Unknown Album")
                release_date = album_data.get("release_date")
                release_year = extract_release_year(release_date)
                
                # Get artist name (primary artist)
                artists = album_data.get("artists", [])
                artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
            
            # Add to set (automatically handles duplicates)
            artist_albums.add((artist_name, album_name, release_year))
        
        # Check if there are more items
        if data.get("next"):
            offset += limit
        else:
            break
    
    return artist_albums


def get_playlist_artists_and_albums(spotify_client: SpotifyClient, playlist_id: str) -> Set[Tuple[str, str, Optional[int]]]:
    """
    Get all unique artist-album-year tuples from a Spotify playlist.
    
    Returns:
        Set of tuples (artist, album, year)
    """
    if not spotify_client.access_token:
        raise Exception("Spotify API authentication required. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
    
    artist_albums = set()
    url = f"{spotify_client.base_url}/playlists/{playlist_id}/tracks"
    headers = spotify_client._get_headers()
    offset = 0
    limit = 100
    
    while True:
        params = {"limit": limit, "offset": offset}
        response = requests.get(url, headers=headers, params=params, timeout=spotify_client.timeout)
        
        if response.status_code != 200:
            break
        
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            break
        
        for item in items:
            track_data = item.get("track")
            if not track_data or track_data is None:
                continue
            
            # Get artist name
            artists = track_data.get("artists", [])
            artist_name = artists[0].get("name", "Unknown Artist") if artists else "Unknown Artist"
            
            # Get album name and release date
            album_data = track_data.get("album", {})
            album_name = album_data.get("name", "Unknown Album")
            release_date = album_data.get("release_date")
            release_year = extract_release_year(release_date)
            
            # Add to set (automatically handles duplicates)
            artist_albums.add((artist_name, album_name, release_year))
        
        # Check if there are more tracks
        if data.get("next"):
            offset += limit
        else:
            break
    
    return artist_albums


def write_artists_and_albums(
    artist_albums: Set[Tuple[str, str, Optional[int]]], 
    output_file: str,
    format: str = "tsv"
):
    """
    Write artist-album-year tuples to a text file in various formats.
    
    Args:
        artist_albums: Set of tuples (artist, album, year)
        output_file: Path to output text file
        format: Output format - "tsv" (tab-separated), "csv" (comma-separated), 
                "json" (JSON array), or "human" (human-readable with dashes)
    """
    import json
    import csv
    
    # Sort by artist name, then album name, then year
    sorted_pairs = sorted(artist_albums, key=lambda x: (x[0].lower(), x[1].lower(), x[2] or 0))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        if format == "tsv":
            # Tab-separated values (best for parsing, handles most edge cases)
            f.write("Artist\tAlbum\tYear\n")  # Header
            for artist, album, year in sorted_pairs:
                year_str = str(year) if year else ""
                f.write(f"{artist}\t{album}\t{year_str}\n")
        
        elif format == "csv":
            # Comma-separated values (standard, but commas in names need quoting)
            writer = csv.writer(f)
            writer.writerow(["Artist", "Album", "Year"])  # Header
            for artist, album, year in sorted_pairs:
                writer.writerow([artist, album, year if year else ""])
        
        elif format == "json":
            # JSON format (most robust, handles all edge cases)
            data = [
                {
                    "artist": artist,
                    "album": album,
                    "year": year
                }
                for artist, album, year in sorted_pairs
            ]
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        elif format == "human":
            # Human-readable format (original format)
            for artist, album, year in sorted_pairs:
                if year:
                    f.write(f"{artist} - {album} ({year})\n")
                else:
                    f.write(f"{artist} - {album}\n")
        
        else:
            raise ValueError(f"Unknown format: {format}. Use 'tsv', 'csv', 'json', or 'human'")
    
    print(f"✓ Wrote {len(sorted_pairs)} artist-album pairs to {output_file} ({format.upper()} format)")


def parse_collection_url(url: str) -> Optional[dict]:
    """
    Parse a Spotify collection/library URL.
    
    Returns:
        Dict with 'type' ('collection') and 'user_id', or None if invalid
    """
    # Pattern for collection URLs like:
    # https://open.spotify.com/user/{user_id}/collection
    # https://open.spotify.com/user/{user_id}/collection?si=...
    pattern = r"open\.spotify\.com/user/([a-zA-Z0-9]+)/collection"
    match = re.search(pattern, url)
    if match:
        return {"type": "collection", "user_id": match.group(1)}
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Parse a Spotify playlist URL or user collection and write all artists and albums to a text file.'
    )
    parser.add_argument(
        'url',
        help='Spotify playlist URL or collection URL (e.g., https://open.spotify.com/playlist/... or https://open.spotify.com/user/{user_id}/collection)'
    )
    parser.add_argument(
        '-o', '--output',
        default='playlist_artists_albums.txt',
        help='Output text file path (default: playlist_artists_albums.txt)'
    )
    parser.add_argument(
        '--format',
        choices=['tsv', 'csv', 'json', 'human'],
        default='tsv',
        help='Output format: tsv (tab-separated, best for parsing), csv (comma-separated), json (JSON array), or human (human-readable). Default: tsv'
    )
    parser.add_argument(
        '--user-token',
        help='User access token with user-library-read scope (required for collection URLs). Get one at: https://developer.spotify.com/console/get-current-user-saved-tracks/ or see: https://developer.spotify.com/documentation/web-api/concepts/scopes#user-library-read'
    )
    parser.add_argument(
        '--collection-type',
        choices=['tracks', 'albums', 'both'],
        default='tracks',
        help='Type of collection to parse: tracks (liked songs), albums (saved albums), or both (default: tracks)'
    )
    
    args = parser.parse_args()
    
    # Initialize Spotify client
    spotify_client = SpotifyClient()
    
    # Check if it's a collection URL
    collection_parsed = parse_collection_url(args.url)
    
    if collection_parsed:
        # Handle collection URL
        user_token = args.user_token or os.getenv("SPOTIFY_USER_ACCESS_TOKEN")
        
        if not user_token:
            print("✗ User access token required for parsing collections.")
            print("\nTo get a user access token:")
            print("  1. Go to: https://developer.spotify.com/console/get-current-user-saved-tracks/")
            print("  2. Click 'Get Token' and authorize with 'user-library-read' scope")
            print("  3. Copy the access token")
            print("  4. Use it with: --user-token <token>")
            print("     Or set SPOTIFY_USER_ACCESS_TOKEN environment variable")
            print("\nFor more information about scopes:")
            print("  https://developer.spotify.com/documentation/web-api/concepts/scopes#user-library-read")
            sys.exit(1)
        
        try:
            artist_albums = set()
            
            if args.collection_type in ['tracks', 'both']:
                print("Fetching liked songs...")
                tracks = get_user_collection_artists_and_albums(
                    user_token, 
                    spotify_client.base_url, 
                    spotify_client.timeout,
                    "tracks"
                )
                artist_albums.update(tracks)
                print(f"✓ Found {len(tracks)} unique artist-album pairs in liked songs")
            
            if args.collection_type in ['albums', 'both']:
                print("Fetching saved albums...")
                albums = get_user_collection_artists_and_albums(
                    user_token, 
                    spotify_client.base_url, 
                    spotify_client.timeout,
                    "albums"
                )
                artist_albums.update(albums)
                print(f"✓ Found {len(albums)} unique artist-album pairs in saved albums")
            
            if not artist_albums:
                print("✗ No items found in collection")
                sys.exit(1)
            
            print(f"✓ Total: {len(artist_albums)} unique artist-album pairs")
            
            # Write to file
            write_artists_and_albums(artist_albums, args.output, args.format)
            
        except Exception as e:
            error_msg = str(e)
            if "Invalid or expired" in error_msg:
                print(f"✗ {error_msg}")
                print("Please get a new token from: https://developer.spotify.com/console/get-current-user-saved-tracks/")
            else:
                print(f"✗ Error: {error_msg}")
            sys.exit(1)
    
    else:
        # Handle playlist URL
        parsed = spotify_client.parse_spotify_url(args.url)
        if not parsed:
            print(f"✗ Invalid Spotify URL: {args.url}")
            print("\nSupported URL formats:")
            print("  - Playlist: https://open.spotify.com/playlist/{playlist_id}")
            print("  - Playlist URI: spotify:playlist:{playlist_id}")
            print("  - Collection: https://open.spotify.com/user/{user_id}/collection")
            print("\nTo get a playlist URL:")
            print("  1. Open Spotify (web or desktop)")
            print("  2. Navigate to the playlist you want to parse")
            print("  3. Click 'Share' → 'Copy link to playlist'")
            print("  4. Use that URL with this script")
            print("\nTo parse a collection:")
            print("  1. Use your collection URL")
            print("  2. Provide a user access token with --user-token")
            sys.exit(1)
        
        if parsed["type"] != "playlist":
            print(f"✗ URL must be a playlist URL, got: {parsed['type']}")
            print("\nThis script only supports playlist URLs.")
            print("For albums, use the main odysseus application.")
            sys.exit(1)
        
        playlist_id = parsed["id"]
        
        # Get artist-album pairs
        try:
            print(f"Fetching tracks from playlist...")
            artist_albums = get_playlist_artists_and_albums(spotify_client, playlist_id)
            
            if not artist_albums:
                print("✗ No tracks found in playlist")
                sys.exit(1)
            
            print(f"✓ Found {len(artist_albums)} unique artist-album pairs")
            
            # Write to file
            write_artists_and_albums(artist_albums, args.output, args.format)
            
        except Exception as e:
            error_msg = str(e)
            if "authentication required" in error_msg.lower():
                print(f"✗ Spotify API authentication required.")
                print("⚠ Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
                print("ℹ You can get these from: https://developer.spotify.com/dashboard")
                print("ℹ Create an app and add the credentials as environment variables.")
            else:
                print(f"✗ Error: {error_msg}")
            sys.exit(1)


if __name__ == "__main__":
    main()

