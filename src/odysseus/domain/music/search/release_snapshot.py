"""Snapshot of unpaginated release-search provider candidates."""

from dataclasses import dataclass
from typing import List

from ....models.search_results import MusicBrainzSong


@dataclass
class ReleaseSearchSnapshot:
    """Unpaginated provider candidates retained for local refinements."""

    fetch_limit: int
    musicbrainz: List[MusicBrainzSong]
    discogs: List[MusicBrainzSong]
    spotify: List[MusicBrainzSong]
    apple_music: List[MusicBrainzSong]

    def has_results(self) -> bool:
        """Return whether at least one provider supplied a candidate."""
        return any(
            (self.musicbrainz, self.discogs, self.spotify, self.apple_music)
        )
