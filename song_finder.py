#!/usr/bin/env python3
"""
Song Finder Script
A script that searches MusicBrainz for song data, allows user selection,
searches YouTube for the selected song, and optionally downloads the video.
"""

import sys
from typing import List, Optional, Dict, Any
from searcher import MusicBrainzSearcher, SongData, MusicBrainzResult
from yt_scrapper import YoutubeSearch
from downloader import YouTubeDownloader


def get_user_input() -> SongData:
    """Get song information from user input."""
    print("=== Song Finder ===")
    print("Enter song information (press Enter to skip optional fields):")
    print()
    
    title = input("Song title: ").strip()
    artist = input("Artist: ").strip()
    album = input("Album (optional): ").strip() or None
    year_input = input("Release year (optional): ").strip()
    
    year = None
    if year_input:
        try:
            year = int(year_input)
        except ValueError:
            print("Invalid year format. Proceeding without year.")
    
    return SongData(
        title=title,
        artist=artist,
        album=album,
        release_year=year
    )


def display_search_results(results: List[MusicBrainzResult]) -> None:
    """Display MusicBrainz search results in a formatted way."""
    if not results:
        print("No results found in MusicBrainz.")
        return
    
    print(f"\n=== MUSICBRAINZ SEARCH RESULTS ===")
    print("-" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"{i}. {result.title or result.album}")
        print(f"   Artist: {result.artist}")
        if result.album and result.title:  # Only show album if we have a title
            print(f"   Album: {result.album}")
        if result.release_date:
            print(f"   Release Date: {result.release_date}")
        print(f"   Score: {result.score}")
        print()


def get_user_selection(results: List[MusicBrainzResult]) -> Optional[MusicBrainzResult]:
    """Get user selection from search results."""
    if not results:
        return None
    
    while True:
        try:
            choice = input(f"Select a result (1-{len(results)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(results):
                return results[choice_num - 1]
            else:
                print(f"Please enter a number between 1 and {len(results)}")
                
        except ValueError:
            print("Please enter a valid number or 'q' to quit")


def search_youtube(selected_song: MusicBrainzResult) -> List[Dict[str, Any]]:
    """Search YouTube for the selected song."""
    # Create search query from the selected song
    search_query = f"{selected_song.artist} {selected_song.title or selected_song.album}"
    
    print(f"\n=== SEARCHING YOUTUBE ===")
    print(f"Search query: {search_query}")
    print()
    
    try:
        # Search YouTube
        youtube_search = YoutubeSearch(search_query, max_results=10)
        videos = youtube_search.videos
        
        if not videos:
            print("No YouTube videos found.")
            return []
        
        print(f"=== YOUTUBE SEARCH RESULTS ===")
        print("-" * 60)
        
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video.get('title', 'No title')}")
            print(f"   Channel: {video.get('channel', 'Unknown')}")
            if video.get('duration'):
                print(f"   Duration: {video.get('duration')}")
            if video.get('views'):
                print(f"   Views: {video.get('views')}")
            if video.get('publish_time'):
                print(f"   Published: {video.get('publish_time')}")
            
            # Construct full YouTube URL
            video_id = video.get('id', '')
            if video_id:
                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                print(f"   URL: {youtube_url}")
            
            print()
        
        return videos
            
    except Exception as e:
        print(f"Error searching YouTube: {e}")
        return []


def get_video_selection(videos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Get user selection from YouTube video results."""
    if not videos:
        return None
    
    while True:
        try:
            choice = input(f"Select a video to download (1-{len(videos)}) or 'q' to skip: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(videos):
                return videos[choice_num - 1]
            else:
                print(f"Please enter a number between 1 and {len(videos)}")
                
        except ValueError:
            print("Please enter a valid number or 'q' to skip")


def download_video(selected_video: Dict[str, Any]) -> None:
    """Download the selected YouTube video."""
    video_id = selected_video.get('id', '')
    if not video_id:
        print("No video ID found.")
        return
    
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"
    video_title = selected_video.get('title', 'Unknown')
    
    print(f"\n=== DOWNLOADING VIDEO ===")
    print(f"Title: {video_title}")
    print(f"URL: {youtube_url}")
    print()
    
    # Ask for download preferences
    print("Download options:")
    print("1. Best quality video")
    print("2. Audio only (MP3)")
    print("3. Specific quality")
    
    choice = input("Choose option (1-3): ").strip()
    
    downloader = YouTubeDownloader()
    
    if choice == "1":
        result = downloader.download_video(youtube_url, quality="best")
    elif choice == "2":
        result = downloader.download_video(youtube_url, audio_only=True)
    elif choice == "3":
        formats = downloader.get_available_formats(youtube_url)
        if formats:
            print("\nAvailable formats:")
            for fmt in formats[:10]:  # Show first 10 formats
                print(f"{fmt['format_code']}: {fmt['extension']} - {fmt['resolution']} - {fmt['note']}")
            
            format_code = input("Enter format code: ").strip()
            result = downloader.download_video(youtube_url, quality=format_code)
        else:
            print("Could not get available formats.")
            result = None
    else:
        print("Invalid choice.")
        result = None
    
    if result:
        print(f"\nDownload completed: {result}")
    else:
        print("\nDownload failed.")


def main():
    """Main function."""
    try:
        # Get song data from user
        song_data = get_user_input()
        
        # Validate input
        if not song_data.title and not song_data.album:
            print("Error: Please provide at least a song title or album name.")
            return
        
        if not song_data.artist:
            print("Error: Please provide an artist name.")
            return
        
        print(f"\nSearching MusicBrainz for: {song_data.title or song_data.album} by {song_data.artist}")
        
        # Search MusicBrainz
        searcher = MusicBrainzSearcher()
        results = searcher.search(song_data)
        
        # Display results
        display_search_results(results)
        
        # Get user selection
        selected_song = get_user_selection(results)
        
        if selected_song is None:
            print("No selection made. Exiting.")
            return
        
        print(f"\nSelected: {selected_song.title or selected_song.album} by {selected_song.artist}")
        
        # Search YouTube
        videos = search_youtube(selected_song)
        
        if videos:
            # Ask if user wants to download
            download_choice = input("\nWould you like to download a video? (y/n): ").strip().lower()
            
            if download_choice in ['y', 'yes']:
                # Get video selection
                selected_video = get_video_selection(videos)
                
                if selected_video:
                    # Download the video
                    download_video(selected_video)
                else:
                    print("No video selected for download.")
            else:
                print("No download requested.")
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
