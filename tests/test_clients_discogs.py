"""Tests for Discogs client parsing and format helpers."""

from odysseus.clients.discogs import (
    DiscogsClient,
    extract_discogs_physical_format,
    extract_discogs_release_type,
)

def test_discogs_release_type_prefers_logical_type_over_medium():
    assert extract_discogs_release_type(["Vinyl", "LP", "Album"]) == "Album"
    assert extract_discogs_physical_format(["Vinyl", "LP", "Album"]) == "Vinyl"
    assert extract_discogs_release_type(
        [{"name": "Vinyl", "descriptions": ["Album", "LP"]}]
    ) == "Album"

def test_discogs_details_use_artist_fields_and_preserve_hyphenated_title():
    client = DiscogsClient.__new__(DiscogsClient)

    release = client._parse_release_info(
        {
            "id": 123,
            "title": "Part One - Part Two",
            "year": 2020,
            "artists": [
                {"name": "First Artist", "join": "&"},
                {"name": "Second Artist"},
            ],
            "formats": [{"name": "CD", "descriptions": ["Album"]}],
            "tracklist": [],
        }
    )

    assert release.title == "Part One - Part Two"
    assert release.artist == "First Artist & Second Artist"

def test_discogs_parser_skips_headings_and_flattens_index_subtracks():
    client = DiscogsClient.__new__(DiscogsClient)

    release = client._parse_release_info(
        {
            "id": 1,
            "title": "Album",
            "artists": [{"name": "Artist"}],
            "tracklist": [
                {"type_": "heading", "title": "Side A"},
                {"type_": "track", "title": "First", "duration": "1:00"},
                {
                    "type_": "index",
                    "title": "Suite",
                    "sub_tracks": [
                        {"type_": "track", "title": "Part One"},
                        {"type_": "track", "title": "Part Two"},
                    ],
                },
            ],
        }
    )

    assert [(track.position, track.title) for track in release.tracks] == [
        (1, "First"),
        (2, "Part One"),
        (3, "Part Two"),
    ]
