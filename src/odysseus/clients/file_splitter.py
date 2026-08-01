"""
File Splitter Module
Handles splitting full album videos into individual tracks using ffmpeg.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from .path_utils import PathUtils
from ..utils.file_duration_reader import (
    get_file_duration,
    parse_duration_to_seconds,
)


class FileSplitter:
    """Splits full album videos into individual tracks."""

    @staticmethod
    def _is_existing_split_valid(
        file_path: Path,
        timestamp_info: Dict[str, Any],
    ) -> bool:
        """Return whether an existing file plausibly matches its track boundary."""
        actual_duration = get_file_duration(file_path)
        start_time = timestamp_info.get("start_time")
        end_time = timestamp_info.get("end_time")
        expected_duration = None
        if start_time is not None and end_time is not None:
            expected_duration = end_time - start_time
        if not expected_duration:
            track = timestamp_info.get("track")
            expected_duration = parse_duration_to_seconds(
                getattr(track, "duration", None)
            )

        # Preserve files we cannot assess; only overwrite proven bad splits.
        if not actual_duration or not expected_duration:
            return True
        tolerance = max(12.0, expected_duration * 0.20)
        return abs(actual_duration - expected_duration) <= tolerance

    @staticmethod
    def _get_existing_files_before_split(
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        audio_extensions: List[str]
    ) -> set:
        """Get set of files that exist before splitting."""
        existing_files_before_split = set()

        for timestamp_info in track_timestamps:
            track = timestamp_info.get('track')
            if not track:
                continue

            from .path_utils import PathUtils
            title = PathUtils.sanitize_filename(track.title)
            track_position = getattr(track, 'position', 0)
            track_prefix = f"{track_position:02d} - " if track_position else ""
            expected_base = f"{track_prefix}{title}"

            found_existing = False
            for ext in audio_extensions:
                potential_file = output_dir / f"{expected_base}{ext}"
                if (
                    potential_file.exists()
                    and potential_file.is_file()
                    and FileSplitter._is_existing_split_valid(
                        potential_file,
                        timestamp_info,
                    )
                ):
                    existing_files_before_split.add(potential_file)
                    found_existing = True
                    break

            if not found_existing:
                existing_files = [
                    f for f in output_dir.glob(f"{expected_base}*")
                    if f.is_file() and f.suffix.lower() in audio_extensions
                ]
                valid_existing_files = [
                    file_path for file_path in existing_files
                    if FileSplitter._is_existing_split_valid(
                        file_path,
                        timestamp_info,
                    )
                ]
                if valid_existing_files:
                    existing_files_before_split.add(valid_existing_files[0])

        return existing_files_before_split

    @staticmethod
    def split_video_into_tracks(
        video_path: Path,
        track_timestamps: List[Dict[str, Any]],
        output_dir: Path,
        metadata_list: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
        audio_format: str = "mp3",
    ) -> List[Optional[Path]]:
        """
        Split a full album video into individual tracks using ffmpeg.

        Args:
            video_path: Path to the full album video file
            track_timestamps: List of dicts with 'start_time' (seconds) and 'end_time' (seconds) for each track
            output_dir: Directory to save split tracks
            metadata_list: List of metadata dicts for each track (must match track_timestamps length)
            progress_callback: Optional callback for progress updates
            audio_format: Configured output format for newly split tracks

        Returns:
            List of paths aligned with ``track_timestamps``. Failed splits are
            ``None`` so callers can pair results by index safely.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if len(track_timestamps) != len(metadata_list):
            raise ValueError("track_timestamps and metadata_list must have the same length")

        encoder_args = {
            "mp3": ["-acodec", "libmp3lame", "-b:a", "320k"],
            "flac": ["-acodec", "flac"],
            "ogg": ["-acodec", "libvorbis", "-q:a", "8"],
            "wav": ["-acodec", "pcm_s16le"],
        }
        audio_format = audio_format.lower()
        if audio_format not in encoder_args:
            raise ValueError(f"Unsupported split audio format: {audio_format}")

        output_files: List[Optional[Path]] = [None] * len(track_timestamps)
        audio_extensions = ['.mp3', '.m4a', '.ogg', '.opus', '.flac', '.wav', '.aac', '.webm']
        system_files = {'.DS_Store', '.Thumbs.db', 'desktop.ini'}

        # Get existing files before splitting
        existing_files_before = FileSplitter._get_existing_files_before_split(track_timestamps, output_dir, audio_extensions)

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

            if (
                file_already_exists
                and not FileSplitter._is_existing_split_valid(
                    output_path,
                    timestamp_info,
                )
            ):
                print(
                    f"Replacing invalid existing split: {output_path.name}"
                )
                file_already_exists = False
                output_path = None

            # If file doesn't exist, create the path for splitting
            if not output_path:
                output_filename = f"{expected_base}.{audio_format}"
                output_path = output_dir / output_filename

            # If file already exists, skip splitting and record the path
            if file_already_exists:
                output_files[i] = output_path
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
                *encoder_args[audio_format],
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
                    output_files[i] = output_path

            except subprocess.CalledProcessError as e:
                print(f"Error splitting track {i+1}: {e.stderr if e.stderr else e}")
            except subprocess.TimeoutExpired:
                print(f"Timeout splitting track {i+1}")

        if progress_callback:
            progress_callback({
                'percent': 100.0,
                'status': 'completed',
                'speed': None,
                'eta': None
            })

        return output_files
