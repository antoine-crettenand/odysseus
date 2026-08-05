"""Align YouTube chapters to album tracklists."""

from typing import List, Optional, Dict, Any, Tuple


class ChapterAligner:
    """Score and align video chapters to release tracks."""

    def __init__(self, video_validator, title_matcher, presenter=None):
        self.video_validator = video_validator
        self.title_matcher = title_matcher
        self.presenter = presenter

    def _calculate_track_timestamps_from_durations(
        self,
        tracks: List,
        track_numbers: List[int]
    ) -> List[Dict[str, Any]]:
        """Calculate track timestamps from MusicBrainz durations."""
        timestamps = []
        current_time = 0.0

        # Advance through the complete album so a partial selection keeps its
        # real offset in the full-album video.
        sorted_tracks = sorted(tracks, key=lambda track: track.position)
        selected_positions = set(track_numbers)
        if not selected_positions:
            return []
        last_selected_position = max(selected_positions)

        for track in sorted_tracks:
            if track.position > last_selected_position:
                break
            duration_seconds = self.video_validator._parse_duration_to_seconds(track.duration)
            if not duration_seconds:
                # A guessed duration before a selected track changes every later
                # boundary and can silently return audio from the wrong song.
                return []

            start_time = current_time
            end_time = start_time + duration_seconds
            current_time = end_time

            if track.position in selected_positions:
                timestamps.append({
                    'start_time': start_time,
                    'end_time': end_time,
                    'track': track
                })

        return timestamps

    def _chapter_title_score(self, chapter_title: str, track_title: str) -> Optional[float]:
        """Return a fuzzy chapter/track title score, or None for generic labels."""
        normalize = self.title_matcher._normalize_for_matching
        chapter = normalize(chapter_title)
        track = normalize(track_title)
        if not chapter or not track:
            return None

        generic_tokens = {
            "chapter",
            "track",
            "side",
            "part",
            "intro",
            "introduction",
            "outro",
            "credits",
        }
        chapter_word_list = [
            word for word in chapter.split()
            if not word.isdigit() and word not in generic_tokens
        ]
        track_word_list = [
            word for word in track.split()
            if not word.isdigit()
        ]
        if not chapter_word_list:
            return None
        chapter_core = " ".join(chapter_word_list)
        track_core = " ".join(track_word_list)
        if chapter_core == track_core:
            return 1.0
        if (
            len(chapter_core) >= 4
            and len(track_core) >= 4
            and (chapter_core in track_core or track_core in chapter_core)
        ):
            return 0.9
        chapter_words = set(chapter_word_list)
        track_words = set(track_word_list)
        if not track_words:
            return 0.0
        return len(chapter_words & track_words) / len(chapter_words | track_words)

    def _chapter_end_time(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
    ) -> Optional[float]:
        """Return the explicit chapter end, falling back to the next boundary."""
        end_time = chapters[chapter_index].get("end_time")
        if end_time is not None:
            return float(end_time)
        if chapter_index + 1 < len(chapters):
            next_start = chapters[chapter_index + 1].get("start_time")
            return float(next_start) if next_start is not None else None
        return None

    def _chapter_duration_score(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
        track,
    ) -> Optional[float]:
        """Score how closely one chapter duration matches release metadata."""
        expected = self.video_validator._parse_duration_to_seconds(track.duration)
        start_time = chapters[chapter_index].get("start_time")
        end_time = self._chapter_end_time(chapters, chapter_index)
        if not expected or start_time is None or end_time is None:
            return None
        actual = end_time - float(start_time)
        if actual <= 0:
            return 0.0
        return min(actual, expected) / max(actual, expected)

    def _validate_aligned_timestamps(
        self,
        timestamps: List[Dict[str, Any]],
        silent: bool,
    ) -> bool:
        """Reject boundaries that would create implausibly short/long tracks."""
        for timestamp in timestamps:
            track = timestamp["track"]
            expected = self.video_validator._parse_duration_to_seconds(track.duration)
            start_time = timestamp.get("start_time")
            end_time = timestamp.get("end_time")
            if start_time is None or end_time is None:
                continue
            actual = end_time - start_time
            if actual <= 0:
                if not silent:
                    self.presenter.log_warning(
                        f"Invalid chapter boundaries for '{track.title}'"
                    )
                return False
            if expected:
                tolerance = max(12.0, expected * 0.20)
                if abs(actual - expected) > tolerance:
                    if not silent:
                        self.presenter.log_warning(
                            f"Chapter for '{track.title}' is {actual:.0f}s, "
                            f"expected about {expected:.0f}s; rejecting video"
                        )
                    return False
        return True

    def _align_chapters_to_tracks(
        self,
        chapters: List[Dict[str, Any]],
        album_tracks: List,
        selected_tracks: List,
        silent: bool,
    ) -> List[Dict[str, Any]]:
        """Align an album tracklist to a chapter subsequence by title/duration."""
        ordered_tracks = sorted(album_tracks, key=lambda track: track.position)
        ordered_chapters = sorted(
            chapters,
            key=lambda chapter: float(chapter.get("start_time", 0)),
        )
        chapter_titles = " ".join(
            str(chapter.get("title") or "")
            for chapter in ordered_chapters
        )
        if self.video_validator.is_vinyl_or_listening_upload(
            "",
            {"description": chapter_titles},
        ):
            if not silent:
                self.presenter.log_warning(
                    "Chapter names indicate vinyl playback or a listening "
                    "session; rejecting video"
                )
            return []

        track_count = len(ordered_tracks)
        chapter_count = len(ordered_chapters)
        if not track_count or chapter_count < track_count:
            if not silent:
                self.presenter.log_warning(
                    f"Chapter count ({chapter_count}) is below album track "
                    f"count ({track_count}); rejecting video"
                )
            return []

        extra_count = chapter_count - track_count
        max_extras = max(2, track_count // 5)
        if extra_count > max_extras:
            if not silent:
                self.presenter.log_warning(
                    f"Too many extra chapters ({chapter_count} chapters for "
                    f"{track_count} tracks); rejecting video"
                )
            return []

        best_indices, best_score = self._best_chapter_alignment(
            ordered_chapters,
            ordered_tracks,
        )

        if best_indices is None or best_score < 0.60:
            if not silent:
                self.presenter.log_warning(
                    f"Chapters do not align confidently with the tracklist "
                    f"(score {max(best_score, 0):.2f}); rejecting video"
                )
            return []

        selected_positions = {track.position for track in selected_tracks}
        timestamps = []
        for chapter_index, track in zip(best_indices, ordered_tracks):
            if track.position not in selected_positions:
                continue
            chapter = ordered_chapters[chapter_index]
            timestamps.append({
                "start_time": float(chapter.get("start_time", 0)),
                "end_time": self._chapter_end_time(
                    ordered_chapters,
                    chapter_index,
                ),
                "chapter_title": chapter.get("title", ""),
                "track": track,
            })

        if not self._validate_aligned_timestamps(timestamps, silent):
            return []

        skipped = [
            ordered_chapters[index].get("title", "")
            for index in set(range(chapter_count)) - set(best_indices)
        ]
        if not silent:
            extra_note = f"; skipped: {', '.join(filter(None, skipped))}" if skipped else ""
            self.presenter.log_info(
                f"Aligned {track_count} tracks to {chapter_count} chapters "
                f"(confidence {best_score:.2f}{extra_note})",
                icon="✓",
            )
        return timestamps

    def _chapter_pair_score(
        self,
        chapters: List[Dict[str, Any]],
        chapter_index: int,
        track,
    ) -> float:
        """Score one ordered chapter/track pairing."""
        title_score = self._chapter_title_score(
            chapters[chapter_index].get("title", ""),
            track.title,
        )
        duration_score = self._chapter_duration_score(
            chapters,
            chapter_index,
            track,
        )
        if title_score is None and duration_score is None:
            return 0.0
        if title_score is None:
            return duration_score
        if duration_score is None:
            return title_score
        return title_score * 0.7 + duration_score * 0.3

    def _best_chapter_alignment(
        self,
        ordered_chapters: List[Dict[str, Any]],
        ordered_tracks: List,
    ) -> Tuple[Optional[Tuple[int, ...]], float]:
        """
        Align tracks to an order-preserving chapter subsequence.

        Uses O(tracks * chapters) dynamic programming instead of enumerating
        combinations, so large albums with a few intro/outro chapters stay safe.
        """
        track_count = len(ordered_tracks)
        chapter_count = len(ordered_chapters)
        if not track_count or chapter_count < track_count:
            return None, -1.0

        neg = float("-inf")
        dp = [[neg] * (chapter_count + 1) for _ in range(track_count + 1)]
        choice = [[None] * (chapter_count + 1) for _ in range(track_count + 1)]
        dp[0][0] = 0.0
        for chapter_used in range(1, chapter_count + 1):
            dp[0][chapter_used] = 0.0
            choice[0][chapter_used] = "skip"

        for track_used in range(1, track_count + 1):
            for chapter_used in range(track_used, chapter_count + 1):
                # Skip this chapter (keep the same number of matched tracks).
                if dp[track_used][chapter_used - 1] > dp[track_used][chapter_used]:
                    dp[track_used][chapter_used] = dp[track_used][chapter_used - 1]
                    choice[track_used][chapter_used] = "skip"

                previous = dp[track_used - 1][chapter_used - 1]
                if previous == neg:
                    continue
                candidate = previous + self._chapter_pair_score(
                    ordered_chapters,
                    chapter_used - 1,
                    ordered_tracks[track_used - 1],
                )
                if candidate > dp[track_used][chapter_used]:
                    dp[track_used][chapter_used] = candidate
                    choice[track_used][chapter_used] = "match"

        best_sum = dp[track_count][chapter_count]
        if best_sum == neg:
            return None, -1.0

        indices: List[int] = []
        track_used = track_count
        chapter_used = chapter_count
        while track_used > 0:
            action = choice[track_used][chapter_used]
            if action == "match":
                indices.append(chapter_used - 1)
                track_used -= 1
                chapter_used -= 1
            elif action == "skip":
                chapter_used -= 1
            else:
                return None, -1.0

        indices.reverse()
        if len(indices) != track_count:
            return None, -1.0
        return tuple(indices), best_sum / track_count
