"""Catalog/release search and track-selection helpers for the desktop controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from ...core.validation import validate_year_range
from ...domain.music.common.date_utils import (
    extract_year,
    format_release_date_label,
    get_original_release_year,
)
from ...models.search_results import MusicBrainzSong

if TYPE_CHECKING:
    from .controller import OdysseusController


class CatalogController:
    """Plain helper owning catalog/track row state and search flows."""

    def __init__(self, host: OdysseusController) -> None:
        self._host = host
        self.releases: List[MusicBrainzSong] = []
        self.rows: List[dict] = []
        self.all_releases: List[MusicBrainzSong] = []
        self.all_rows: List[dict] = []
        self.selected_index = -1
        self.release_info = None
        self.track_rows: List[dict] = []

    @property
    def selected_track_count(self) -> int:
        return sum(bool(row["selected"]) for row in self.track_rows)

    @property
    def can_download_release(self) -> bool:
        return not self._host._busy and any(
            row["selected"] for row in self.track_rows
        )

    def parse_year_filters(
        self,
        year_text: str,
        year_from_text: str,
        year_to_text: str,
    ):
        year = int(year_text.strip()) if year_text.strip() else None
        year_from = int(year_from_text.strip()) if year_from_text.strip() else None
        year_to = int(year_to_text.strip()) if year_to_text.strip() else None
        validate_year_range(year, year_from, year_to)
        return year, year_from, year_to

    def clear(self) -> None:
        host = self._host
        self.releases = []
        self.rows = []
        self.all_releases = []
        self.all_rows = []
        self.selected_index = -1
        self.release_info = None
        self.track_rows = []
        host.catalogResultsChanged.emit()
        host.tracksChanged.emit()
        host.selectionChanged.emit()

    def filter_results(self, query: str) -> None:
        """Filter loaded releases locally while keeping row/release indexes aligned."""
        host = self._host
        terms = query.casefold().split()
        if not terms:
            self.releases = list(self.all_releases)
            self.rows = list(self.all_rows)
        else:
            matches = []
            for release, row in zip(self.all_releases, self.all_rows):
                searchable = " ".join(
                    str(value)
                    for value in (
                        row.get("title", ""),
                        row.get("artist", ""),
                        row.get("date", ""),
                        row.get("year", ""),
                        row.get("editionYear", ""),
                        row.get("type", ""),
                        row.get("source", ""),
                        row.get("editionDetail", ""),
                        row.get("identifierDetail", ""),
                    )
                ).casefold()
                if all(term in searchable for term in terms):
                    matches.append((release, row))
            self.releases = [release for release, _ in matches]
            self.rows = [row for _, row in matches]

        # A visible index may refer to a different release after filtering.
        self.selected_index = -1
        self.release_info = None
        self.track_rows = []
        host.catalogResultsChanged.emit()
        host.tracksChanged.emit()
        host.selectionChanged.emit()

    def search_albums(
        self,
        album: str,
        artist: str,
        year_text: str,
        release_type: str,
        year_from_text: str = "",
        year_to_text: str = "",
    ) -> None:
        host = self._host
        if host._busy or host.release_workflow is None:
            return
        album = album.strip()
        artist = artist.strip()
        if not album or not artist:
            host._set_status("Album and artist are required.", "#ff8797")
            return
        try:
            year, year_from, year_to = self.parse_year_filters(
                year_text,
                year_from_text,
                year_to_text,
            )
        except ValueError as error:
            host._set_status(str(error), "#ff8797")
            return
        self.clear()
        host._set_status("Searching release providers…", "#71d7ff")
        host._start_worker(
            lambda: host.release_workflow.search_releases(
                album,
                artist,
                year=year,
                year_from=year_from,
                year_to=year_to,
                release_type=release_type or None,
            ),
            self.on_catalog_found,
        )

    def search_discography(
        self,
        artist: str,
        year_text: str,
        release_type: str,
        include_compilations: bool,
        year_from_text: str = "",
        year_to_text: str = "",
    ) -> None:
        host = self._host
        if host._busy or host.release_workflow is None:
            return
        artist = artist.strip()
        if not artist:
            host._set_status("Artist is required.", "#ff8797")
            return
        try:
            year, year_from, year_to = self.parse_year_filters(
                year_text,
                year_from_text,
                year_to_text,
            )
        except ValueError as error:
            host._set_status(str(error), "#ff8797")
            return
        self.clear()
        host._set_status("Loading artist discography…", "#71d7ff")
        host._start_worker(
            lambda: host.release_workflow.search_discography(
                artist,
                year=year,
                year_from=year_from,
                year_to=year_to,
                release_type=release_type or None,
                include_compilations=include_compilations,
            ),
            self.on_catalog_found,
        )

    def select_release(self, index: int) -> None:
        host = self._host
        if (
            host._busy
            or host.release_workflow is None
            or not 0 <= index < len(self.releases)
        ):
            return
        self.selected_index = index
        self.release_info = None
        self.track_rows = []
        host.tracksChanged.emit()
        host.selectionChanged.emit()
        release = self.releases[index]
        host._set_status("Loading track listing…", "#71d7ff")
        host._start_worker(
            lambda: host.release_workflow.get_release_info(release),
            self.on_release_loaded,
        )

    def toggle_track(self, index: int) -> None:
        host = self._host
        if host._busy or not 0 <= index < len(self.track_rows):
            return
        self.track_rows[index]["selected"] = not self.track_rows[index]["selected"]
        host.tracksChanged.emit()

    def select_all_tracks(self, selected: bool) -> None:
        host = self._host
        if host._busy:
            return
        for row in self.track_rows:
            row["selected"] = selected
        host.tracksChanged.emit()

    def on_catalog_found(self, releases: List[MusicBrainzSong]) -> None:
        host = self._host
        self.all_releases = sorted(
            releases,
            key=lambda release: (
                get_original_release_year(release) is None,
                get_original_release_year(release) or 0,
            ),
        )
        self.all_rows = []
        for item in self.all_releases:
            original_year = extract_year(item.original_release_date)
            edition_year = extract_year(item.release_date)
            cover_art_url = item.cover_art_url or ""
            if (
                not cover_art_url
                and item.source.casefold() == "musicbrainz"
                and item.mbid
            ):
                cover_art_url = (
                    "https://coverartarchive.org/release/"
                    f"{item.mbid}/front-250"
                )
            has_distinct_edition = bool(
                original_year
                and edition_year
                and original_year != edition_year
            )
            source_key = item.source.casefold()
            source_name = {
                "applemusic": "Apple Music",
                "musicbrainz": "MusicBrainz",
            }.get(source_key, item.source.title())
            edition_parts = []
            if item.country:
                edition_parts.append(item.country)
            if item.media_format:
                edition_parts.append(item.media_format)
            if item.label:
                edition_parts.append(item.label)
            if item.catalog_number:
                edition_parts.append(item.catalog_number)
            if item.track_count:
                edition_parts.append(f"{item.track_count} tracks")
            identifier_parts = []
            if item.barcode:
                identifier_parts.append(f"UPC/EAN {item.barcode}")
            if item.release_status:
                identifier_parts.append(item.release_status.title())
            self.all_rows.append(
                {
                    "title": item.album or item.title or "Unknown release",
                    "artist": item.artist or "Unknown artist",
                    "date": format_release_date_label(item),
                    "year": original_year or edition_year or "—",
                    "yearKind": "Original" if original_year else "Release",
                    "editionYear": edition_year if has_distinct_edition else "",
                    "isReissue": has_distinct_edition,
                    "coverArtUrl": cover_art_url,
                    "editionDetail": " · ".join(edition_parts),
                    "identifierDetail": " · ".join(identifier_parts),
                    "type": item.release_type or "Release",
                    "source": source_name,
                }
            )
        self.releases = list(self.all_releases)
        self.rows = list(self.all_rows)
        host.catalogResultsChanged.emit()
        if releases:
            host._set_status(
                f"Found {len(releases)} release(s). Select one to view tracks.",
                "#7ce7b2",
            )
        else:
            host._set_status("No matching releases found.", "#ffc66d")

    def on_release_loaded(self, release_info) -> None:
        host = self._host
        self.release_info = release_info
        self.track_rows = [
            {
                "position": track.position,
                "title": track.title,
                "artist": track.artist or release_info.artist,
                "duration": track.duration or "—",
                "selected": True,
            }
            for track in release_info.tracks
        ]
        host.tracksChanged.emit()
        host._set_status(
            f"Loaded {len(self.track_rows)} tracks from {release_info.title}.",
            "#7ce7b2",
        )
