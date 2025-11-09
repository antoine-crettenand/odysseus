"""
File Splitter Module
Handles splitting full album videos into individual tracks using ffmpeg.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from .path_utils import PathUtils


class FileSplitter:
    """Splits full album videos into individual tracks."""
    
    @staticmethod
    def split_video_into_tracks(
        video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None
    ) -> List[Path]:
        """
        Split a full album video into individual tracks using ffmpeg.
        
        Args:
            video_path: Path to the full album video file
            track_timestamps: List of dicts with 'start_time' (seconds) and 'end_time' (seconds) for each track
            output_dir: Directory to save split tracks
            metadata_list: List of metadata dicts for each track (must match track_timestamps length)
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of paths to the split track files
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")
        
        if len(track_timestamps) != len(metadata_list):
            raise ValueError("track_timestamps and metadata_list must have the same length")
        
        output_files = []
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}
        
        for i, (timestamp_info, metadata) in enumerate(zip(track_timestamps, metadata_list)):
            start_time = timestamp_info.get('start_time', 0)
            end_time = timestamp_info.get('end_time')
            
            # Create output filename
            title = PathUtils.sanitize_filename(metadata.get('title', f'track_{i+1}'))
            track_number = metadata.get('track_number', i + 1)
            track_prefix = f"{track_number:02d} - " if track_number else ""
            expected_base = f"{track_prefix}{title}"
            
            # Check if file already exists (try different extensions)
            output_path = None
            file_already_exists = False
            
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if potential_file.exists() and potential_file.is_file():
                    output_path = potential_file
                    file_already_exists = True
                    break
            
            # If not found with exact match, try glob pattern
            if not output_path:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file()
                    and f.suffix.lower() in audio_extensions
                    and f.name not in system_files
                ]
                if existing_files:
                    output_path = existing_files[0]
                    file_already_exists = True
            
            # If file doesn't exist, create the path for splitting
            if not output_path:
                output_filename = f"{expected_base}.mp3"
                output_path = output_dir / output_filename
            
            # If file already exists, skip splitting and add to output list
            if file_already_exists:
                output_files.append(output_path)
                if progress_callback:
                    # Update progress
                    progress = ((i + 1) / len(track_timestamps)) * 100
                    progress_callback({
                        'percent': progress,
                        'status': 'skipped',
                        'speed': None,
                        'eta': None
                    })
                continue
            
            # Build ffmpeg command
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', str(start_time),  # Start time
                '-acodec', 'libmp3lame',
                '-ab', '320k',  # High quality audio
                '-y',  # Overwrite output file
            ]
            
            # Add end time if specified
            if end_time:
                duration = end_time - start_time
                cmd.extend(['-t', str(duration)])
            
            cmd.append(str(output_path))
            
            # Run ffmpeg
            try:
                if progress_callback:
                    # For splitting, we can estimate progress based on track number
                    progress = (i / len(track_timestamps)) * 100
                    progress_callback({
                        'percent': progress,
                        'status': 'splitting',
                        'speed': None,
                        'eta': None
                    })
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=300  # 5 minute timeout per track
                )
                
                if output_path.exists():
                    output_files.append(output_path)
                    
            except subprocess.CalledProcessError as e:
                print(f"Error splitting track {i+1}: {e.stderr if e.stderr else e}")
                continue
            except subprocess.TimeoutExpired:
                print(f"Timeout splitting track {i+1}")
                continue
        
        if progress_callback:
            progress_callback({
                'percent': 100.0,
                'status': 'completed',
                'speed': None,
                'eta': None
            })
        
        return output_files

