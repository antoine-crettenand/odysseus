#!/usr/bin/env python3
"""
Script to fix track 9 "Two Fish And An Elephant" from Khruangbin "The Universe Smiles Upon You ii" (2025)
by finding correct YouTube URL and re-downloading it.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from odysseus.services.search_service import SearchService
from odysseus.services.download_service import DownloadService
from odysseus.services.metadata_service import MetadataService
from odysseus.models.releases import Track, ReleaseInfo
from rich.console import Console

# Only track 9
TRACK_TITLE = "Two Fish And An Elephant ii"  # Include "ii" to match the album version
TRACK_NUM = 9
ARTIST = "Khruangbin"
ALBUM = "The Universe Smiles Upon You ii"
YEAR = "2025"
DOWNLOAD_DIR = Path("/Users/antoinecrettenand/Documents/Ideas/odysseus/downloads/Khruangbin/The Universe Smiles Upon You ii (2025)")

def main():
    console = Console()
    search_service = SearchService()
    download_service = DownloadService()
    metadata_service = MetadataService()
    
    console.print(f"[bold cyan]🔍 Fixing track {TRACK_NUM}: {TRACK_TITLE}[/bold cyan]")
    console.print(f"[cyan]Album: {ALBUM} ({YEAR})[/cyan]")
    console.print()
    
    # Try to find the release in MusicBrainz to get MBID for cover art
    from odysseus.models.song import SongData
    console.print("[blue]ℹ[/blue] Searching for release in MusicBrainz to get cover art...")
    song_data = SongData(title="", artist=ARTIST, album=ALBUM, release_year=int(YEAR))
    mb_releases = search_service.search_releases(song_data, limit=5)
    
    release_mbid = ""
    if mb_releases:
        # Find the one that matches our album title and year
        for mb_release in mb_releases:
            if mb_release.album and ALBUM.lower() in mb_release.album.lower():
                if mb_release.mbid:
                    release_mbid = mb_release.mbid
                    console.print(f"[green]✓ Found release MBID: {release_mbid}[/green]")
                    break
    
    # Create release info for metadata
    release_info = ReleaseInfo(
        title=ALBUM,
        artist=ARTIST,
        release_date=f"{YEAR}-01-01",
        genre=None,
        release_type="Album",
        mbid=release_mbid,
        url="",
        tracks=[Track(position=TRACK_NUM, title=TRACK_TITLE, artist=ARTIST, duration=None)]
    )
    
    # Fetch cover art once
    console.print("[blue]ℹ[/blue] Fetching cover art...")
    cover_art_data = metadata_service.fetch_cover_art_for_release(release_info, console)
    
    # If no cover art from MusicBrainz, try to extract from existing track in folder
    if not cover_art_data:
        console.print("[blue]ℹ[/blue] Trying to extract cover art from existing track in folder...")
        try:
            # Look for other MP3 files in the folder (excluding the one we're about to download)
            existing_files = list(DOWNLOAD_DIR.glob("*.mp3"))
            # Exclude track 9 if it already exists
            existing_files = [f for f in existing_files if "09 -" not in f.name]
            
            if existing_files:
                # Try the first file
                sample_file = existing_files[0]
                console.print(f"[blue]ℹ[/blue] Trying to extract cover art from: {sample_file.name}")
                
                try:
                    from mutagen.mp3 import MP3
                    from mutagen.id3 import ID3NoHeaderError
                    
                    audio_file = MP3(str(sample_file))
                    if audio_file.tags:
                        # Look for APIC (cover art) frames
                        for key in audio_file.tags.keys():
                            if key.startswith('APIC'):
                                apic = audio_file.tags[key]
                                if hasattr(apic, 'data'):
                                    cover_art_data = apic.data
                                    console.print(f"[green]✓ Extracted cover art from {sample_file.name} ({len(cover_art_data)} bytes)[/green]")
                                    break
                except ID3NoHeaderError:
                    # Try with eyed3 as fallback
                    try:
                        import eyed3
                        audiofile = eyed3.load(str(sample_file))
                        if audiofile and audiofile.tag and audiofile.tag.images:
                            # Get the first image
                            image = audiofile.tag.images[0]
                            cover_art_data = image.image_data
                            console.print(f"[green]✓ Extracted cover art from {sample_file.name} ({len(cover_art_data)} bytes)[/green]")
                    except Exception as e:
                        console.print(f"[yellow]⚠[/yellow] Could not extract cover art with eyed3: {e}")
                except Exception as e:
                    console.print(f"[yellow]⚠[/yellow] Could not extract cover art: {e}")
            else:
                console.print(f"[yellow]⚠[/yellow] No existing MP3 files found in folder to extract cover art from")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Error extracting cover art from folder: {e}")
    
    # If still no cover art, try YouTube thumbnail as last resort
    if not cover_art_data:
        console.print("[blue]ℹ[/blue] Trying to get cover art from YouTube thumbnail as last resort...")
        try:
            video_info = download_service.get_video_info("https://www.youtube.com/watch?v=vOhUl-OHj9E")
            if video_info:
                # Try to get thumbnail - YouTube provides high-res thumbnails
                thumbnail_url = video_info.get('thumbnail') or video_info.get('thumbnails', [{}])[0].get('url', '')
                if thumbnail_url:
                    # Try to get maxresdefault thumbnail
                    if 'maxresdefault' not in thumbnail_url:
                        # Replace with maxresdefault if available
                        video_id = "vOhUl-OHj9E"
                        thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                    
                    cover_art_data = metadata_service.fetch_cover_art_from_url(thumbnail_url, console)
                    if cover_art_data:
                        console.print(f"[green]✓ Got cover art from YouTube thumbnail[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not get YouTube thumbnail: {e}")
    
    # Use the provided correct YouTube URL
    correct_url = "https://www.youtube.com/watch?v=vOhUl-OHj9E"
    
    console.print(f"[cyan]Using provided URL: {correct_url}[/cyan]")
    console.print()
    
    try:
        # Get video info to confirm it's the right one
        video_info = download_service.get_video_info(correct_url)
        if video_info:
            video_title = video_info.get('title', 'Unknown')
            console.print(f"[green]Video title: {video_title}[/green]")
        
        # Download the track
        metadata_dict = {
            'title': TRACK_TITLE,
            'artist': ARTIST,
            'album': ALBUM,
            'year': int(YEAR),
            'track_number': TRACK_NUM,
            'total_tracks': 10
        }
        
        console.print(f"[cyan]Downloading...[/cyan]")
        downloaded_path = download_service.download_high_quality_audio(
            correct_url,
            metadata=metadata_dict,
            quiet=True
        )
        
        if downloaded_path:
            # Apply metadata with cover art
            track = Track(position=TRACK_NUM, title=TRACK_TITLE, artist=ARTIST, duration=None)
            try:
                metadata_service.apply_metadata_with_cover_art(
                    downloaded_path, track, release_info, console, cover_art_data=cover_art_data
                )
                console.print(f"[bold green]✓ Successfully downloaded and fixed: {TRACK_TITLE}[/bold green]")
                console.print(f"[green]Path: {downloaded_path}[/green]")
                video_found = True
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Downloaded but metadata failed: {e}")
                video_found = True
        else:
            console.print(f"[red]✗ Download failed[/red]")
            video_found = False
                
    except Exception as e:
        console.print(f"[red]✗ Error downloading: {e}[/red]")
        video_found = False
    
    if not video_found:
        console.print(f"[red]✗ Could not find correct video for: {TRACK_TITLE}[/red]")
        console.print(f"[yellow]⚠[/yellow] You may need to manually search YouTube and download")
    else:
        console.print()
        console.print("[bold green]✓ Track fixed successfully![/bold green]")

if __name__ == "__main__":
    main()

