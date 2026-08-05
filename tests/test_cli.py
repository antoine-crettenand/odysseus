"""Tests for OdysseusCLI exit codes and batch parsing."""

from unittest.mock import MagicMock

import pytest

from odysseus.models.outcomes import OperationOutcome
from odysseus.ui.cli import OdysseusCLI

@pytest.mark.parametrize(
    ("arguments", "handler_name"),
    [
        (
            ["recording", "--title", "Track", "--artist", "Artist"],
            "recording_handler",
        ),
        (
            ["discography", "--artist", "Artist"],
            "discography_handler",
        ),
        (
            ["spotify", "--url", "https://open.spotify.com/album/id"],
            "spotify_handler",
        ),
        (
            ["metadata", "/tmp/missing.mp3", "--artist", "Artist", "--album", "Album"],
            "metadata_handler",
        ),
    ],
)
def test_cli_returns_nonzero_for_handler_failures(arguments, handler_name):
    cli = OdysseusCLI(load_services=False)
    cli.display_manager = MagicMock()
    handler = MagicMock()
    handler.handle.return_value = OperationOutcome.failure("failed")
    setattr(cli, handler_name, handler)

    assert cli.run(arguments) == 1

def test_human_batch_parser_preserves_commas_and_hyphens(tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text(
        "Earth, Wind & Fire - That's the Way of the World (1975)\n"
        "Jay-Z - The Blueprint (2001)\n",
        encoding="utf-8",
    )

    entries = OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))

    assert entries == [
        ("Earth, Wind & Fire", "That's the Way of the World", 1975),
        ("Jay-Z", "The Blueprint", 2001),
    ]

def test_batch_parser_recognizes_csv_after_leading_comments(tmp_path):
    batch_file = tmp_path / "batch.txt"
    batch_file.write_text(
        "# albums\nArtist,Album,Year\nArtist One,Album One,2020\n",
        encoding="utf-8",
    )

    entries = OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))

    assert entries == [("Artist One", "Album One", 2020)]

def test_batch_parser_rejects_explicit_malformed_year(tmp_path):
    batch_file = tmp_path / "batch.csv"
    batch_file.write_text(
        "Artist,Album,Year\nTest Artist,Test Album,20O1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Invalid year on line 2"):
        OdysseusCLI(load_services=False)._parse_batch_file(str(batch_file))
