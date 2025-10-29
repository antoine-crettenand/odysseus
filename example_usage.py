#!/usr/bin/env python3
"""
Example Usage Script
Demonstrates how to use the enhanced metadata merger with all sources.
"""

import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from api_config import APIConfig, create_metadata_merger_with_apis
from metadata_merger import MetadataMerger
from musicbrainz_client import SongData


def main():
    """Main example function."""
    print("=== Odysseus Enhanced Metadata Merger Example ===\n")
    
    # Check API configuration
    config = APIConfig()
    configured_services = config.get_configured_services()
    
    print(f"Configured services: {', '.join(configured_services) if configured_services else 'None'}")
    print()
    
    if not configured_services:
        print("⚠️  No APIs configured. Using MusicBrainz only.")
        print("Run 'python api_config.py' to see setup instructions.\n")
        merger = MetadataMerger()
    else:
        print("✅ Using enhanced metadata merger with all configured APIs.\n")
        merger = create_metadata_merger_with_apis()
    
    # Example song data
    song_data = SongData(
        title="Bohemian Rhapsody",
        artist="Queen",
        album="A Night at the Opera",
        release_year=1975
    )
    
    print(f"Searching for: {song_data.title} by {song_data.artist}")
    print(f"Album: {song_data.album} ({song_data.release_year})")
    print()
    
    # Search all sources
    merger.search_all_sources(
        title=song_data.title,
        artist=song_data.artist,
        album=song_data.album
    )
    
    # Merge metadata
    final_metadata = merger.merge_metadata()
    
    # Print results
    print("=== MERGED METADATA ===")
    print(f"Title: {final_metadata.title}")
    print(f"Artist: {final_metadata.artist}")
    print(f"Album: {final_metadata.album}")
    print(f"Year: {final_metadata.year}")
    print(f"Genre: {final_metadata.genre}")
    print(f"Source: {final_metadata.source}")
    print(f"Has cover art: {'Yes' if final_metadata.cover_art_data else 'No'}")
    if final_metadata.cover_art_data:
        print(f"Cover art size: {len(final_metadata.cover_art_data)} bytes")
    if final_metadata.comment:
        print(f"Comment: {final_metadata.comment}")
    print()
    
    # Print source summary
    summary = merger.get_metadata_summary()
    print("=== SOURCE SUMMARY ===")
    print(f"Total sources: {summary['total_sources']}")
    print()
    
    for source in summary['sources']:
        print(f"📊 {source['name']}")
        print(f"   Confidence: {source['confidence']:.2f}")
        print(f"   Completeness: {source['completeness']:.2f}")
        print(f"   Title: {source['metadata']['title']}")
        print(f"   Artist: {source['metadata']['artist']}")
        if source['metadata']['album']:
            print(f"   Album: {source['metadata']['album']}")
        if source['metadata']['year']:
            print(f"   Year: {source['metadata']['year']}")
        print()
    
    # Example of applying metadata to a file
    print("=== APPLYING METADATA ===")
    example_file = Path("example_song.mp3")
    
    if example_file.exists():
        print(f"Applying metadata to {example_file}...")
        success = merger.apply_metadata_to_file(example_file)
        if success:
            print("✅ Metadata applied successfully!")
        else:
            print("❌ Failed to apply metadata")
    else:
        print(f"Example file {example_file} not found - skipping metadata application")
        print("To test metadata application, place an MP3 file named 'example_song.mp3' in this directory")


def demonstrate_individual_sources():
    """Demonstrate individual source usage."""
    print("\n=== INDIVIDUAL SOURCE DEMONSTRATION ===\n")
    
    config = APIConfig()
    
    # Discogs example
    if config.is_configured('discogs'):
        print("🔍 Discogs Example:")
        from discogs_client import DiscogsClient
        discogs = DiscogsClient(config.get_config('discogs')['token'])
        results = discogs.search_release("Bohemian Rhapsody", "Queen", "A Night at the Opera")
        if results:
            print(f"   Found: {results[0].title} by {results[0].artist}")
            print(f"   Year: {results[0].year}")
            print(f"   Genre: {results[0].genre}")
            print(f"   Label: {results[0].label}")
        print()
    
    # Last.fm example
    if config.is_configured('lastfm'):
        print("🔍 Last.fm Example:")
        from lastfm_client import LastFmClient
        lastfm = LastFmClient(config.get_config('lastfm')['api_key'])
        results = lastfm.search_track("Bohemian Rhapsody", "Queen")
        if results:
            print(f"   Found: {results[0].title} by {results[0].artist}")
            print(f"   Playcount: {results[0].playcount:,}" if results[0].playcount else "   Playcount: N/A")
            print(f"   Listeners: {results[0].listenrs:,}" if results[0].listeners else "   Listeners: N/A")
        print()
    
    # Spotify example
    if config.is_configured('spotify'):
        print("🔍 Spotify Example:")
        from spotify_client import SpotifyClient
        spotify = SpotifyClient(
            config.get_config('spotify')['client_id'],
            config.get_config('spotify')['client_secret']
        )
        results = spotify.search_tracks("Bohemian Rhapsody", "Queen")
        if results:
            print(f"   Found: {results[0].title} by {results[0].artist}")
            print(f"   Popularity: {results[0].popularity}/100")
            print(f"   Duration: {results[0].duration_ms // 60000}:{(results[0].duration_ms % 60000) // 1000:02d}")
        print()
    
    # Genius example
    if config.is_configured('genius'):
        print("🔍 Genius Example:")
        from genius_client import GeniusClient
        genius = GeniusClient(config.get_config('genius')['access_token'])
        results = genius.search_songs("Bohemian Rhapsody", "Queen")
        if results:
            print(f"   Found: {results[0].title} by {results[0].artist}")
            print(f"   URL: {results[0].url}")
        print()


if __name__ == "__main__":
    main()
    demonstrate_individual_sources()
