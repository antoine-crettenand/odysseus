#!/usr/bin/env python3
"""
Script to fix compilation tags and add cover art to existing MP3 files
in the "New Europa..." folder.
"""

import sys
from pathlib import Path
from mutagen.id3 import ID3, TPE2, TCMP, APIC, ID3NoHeaderError
import requests

def fetch_spotify_cover_art(album_name: str):
    """Try to find cover art for the album by searching Spotify."""
    # This is a simple approach - in a real scenario, you'd use the Spotify API
    # For now, we'll return None and let the user manually add cover art
    # or we could search MusicBrainz for the album
    return None

def fix_files_in_directory(directory: Path, album_name: str = None, cover_art_url: str = None):
    """Fix compilation tags and add cover art for all MP3 files in a directory."""
    mp3_files = sorted(list(directory.glob("*.mp3")))
    
    if not mp3_files:
        print(f"No MP3 files found in {directory}")
        return
    
    print(f"Found {len(mp3_files)} MP3 files in {directory}")
    
    # Get album name from first file if not provided
    if album_name is None:
        try:
            tags = ID3(str(mp3_files[0]))
            album_name = tags.get('TALB', ['Unknown Album'])[0] if 'TALB' in tags else 'Unknown Album'
        except:
            album_name = directory.name
    
    print(f"Album: {album_name}")
    print()
    
    # Fetch cover art if URL provided
    cover_art_data = None
    if cover_art_url:
        try:
            # Check if it's a Spotify URL - if so, extract cover art URL from API
            if 'spotify.com' in cover_art_url or 'spotify:' in cover_art_url:
                print(f"Detected Spotify URL, extracting cover art...")
                try:
                    # Try to use Spotify client to get cover art URL
                    import os
                    if os.getenv('SPOTIFY_CLIENT_ID') and os.getenv('SPOTIFY_CLIENT_SECRET'):
                        from src.odysseus.clients.spotify import SpotifyClient
                        spotify_client = SpotifyClient()
                        parsed = spotify_client.parse_spotify_url(cover_art_url)
                        if parsed:
                            if parsed['type'] == 'album':
                                release_info = spotify_client.get_album_tracks(parsed['id'])
                            elif parsed['type'] == 'playlist':
                                release_info = spotify_client.get_playlist_tracks(parsed['id'])
                            else:
                                release_info = None
                            
                            if release_info and release_info.cover_art_url:
                                cover_art_url = release_info.cover_art_url
                                print(f"Found cover art URL: {cover_art_url}")
                            else:
                                print("✗ Could not find cover art URL from Spotify API")
                                cover_art_url = None
                    else:
                        print("⚠ Spotify credentials not set. Cannot extract cover art from Spotify URL.")
                        print("   Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables.")
                        cover_art_url = None
                except Exception as e:
                    print(f"✗ Error extracting cover art from Spotify: {e}")
                    cover_art_url = None
            
            # Fetch the actual image
            if cover_art_url:
                print(f"Fetching cover art from: {cover_art_url}")
                headers = {'User-Agent': 'Odysseus/1.0'}
                response = requests.get(cover_art_url, headers=headers, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    # Check if it's actually an image
                    content_type = response.headers.get('Content-Type', '')
                    if 'image' in content_type or len(response.content) > 1000:
                        cover_art_data = response.content
                        print(f"✓ Fetched cover art ({len(cover_art_data)} bytes, {content_type})")
                    else:
                        print(f"✗ URL did not return an image (Content-Type: {content_type})")
                else:
                    print(f"✗ Failed to fetch cover art: HTTP {response.status_code}")
        except Exception as e:
            print(f"✗ Error fetching cover art: {e}")
        print()
    
    fixed_count = 0
    cover_art_added = 0
    
    for mp3_file in mp3_files:
        try:
            # Try to load existing tags
            try:
                tags = ID3(str(mp3_file))
            except ID3NoHeaderError:
                # Create new tags if none exist
                tags = ID3()
            
            # Set Album Artist to "Various Artists"
            tags['TPE2'] = TPE2(encoding=3, text="Various Artists")
            
            # Set Compilation flag to "1"
            tags['TCMP'] = TCMP(encoding=3, text="1")
            
            # Add cover art if available
            if cover_art_data:
                # Determine MIME type from cover art data (matching main codebase)
                mime_type = "image/jpeg"  # Default to JPEG
                if cover_art_data.startswith(b'\xff\xd8\xff'):
                    mime_type = "image/jpeg"
                elif cover_art_data.startswith(b'\x89PNG'):
                    mime_type = "image/png"
                elif cover_art_data.startswith(b'GIF'):
                    mime_type = "image/gif"
                elif cover_art_data.startswith(b'RIFF'):
                    mime_type = "image/webp"
                
                # Remove all existing APIC frames to avoid duplicates (matching main codebase)
                apic_keys = [key for key in tags.keys() if key.startswith('APIC')]
                for key in apic_keys:
                    try:
                        del tags[key]
                    except:
                        pass
                
                # Add the cover art (matching main codebase method)
                apic = APIC(
                    encoding=3,  # UTF-8
                    mime=mime_type,
                    type=3,  # Cover (front)
                    desc='Cover',
                    data=cover_art_data
                )
                tags.add(apic)  # Use .add() method like main codebase
                cover_art_added += 1
            
            # Save tags
            tags.save()
            fixed_count += 1
            print(f"✓ Fixed: {mp3_file.name}")
            
        except Exception as e:
            print(f"✗ Error fixing {mp3_file.name}: {e}")
    
    print()
    print(f"Fixed {fixed_count} out of {len(mp3_files)} files")
    if cover_art_data:
        print(f"Added cover art to {cover_art_added} files")

if __name__ == "__main__":
    # Find the "New Europa" directory
    downloads_dir = Path("downloads")
    new_europa_dirs = list(downloads_dir.glob("**/New Europa*"))
    
    if not new_europa_dirs:
        print("Error: Could not find 'New Europa' folder in downloads directory")
        sys.exit(1)
    
    if len(new_europa_dirs) > 1:
        print("Found multiple 'New Europa' directories:")
        for i, dir_path in enumerate(new_europa_dirs, 1):
            print(f"  {i}. {dir_path}")
        print()
        choice = input("Enter number to select (or 'all' to fix all): ").strip()
        
        if choice.lower() == 'all':
            for dir_path in new_europa_dirs:
                print(f"\n{'='*60}")
                print(f"Processing: {dir_path}")
                print('='*60)
                fix_files_in_directory(dir_path)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(new_europa_dirs):
                    fix_files_in_directory(new_europa_dirs[idx])
                else:
                    print("Invalid selection")
                    sys.exit(1)
            except ValueError:
                print("Invalid selection")
                sys.exit(1)
    else:
        # Single directory found
        directory = new_europa_dirs[0]
        
        # You can optionally provide a Spotify cover art URL
        # Example: https://i.scdn.co/image/ab67616d0000b273...
        cover_art_url = None
        if len(sys.argv) > 1:
            cover_art_url = sys.argv[1]
            print(f"Using cover art URL: {cover_art_url}")
            print()
        
        fix_files_in_directory(directory, cover_art_url=cover_art_url)

