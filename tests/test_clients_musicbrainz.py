"""Tests for MusicBrainz client parsing helpers."""

from odysseus.clients.musicbrainz import MusicBrainzClient

def test_musicbrainz_artist_credit_preserves_alias_and_joinphrase():
    client = MusicBrainzClient.__new__(MusicBrainzClient)

    artist = client._parse_artist_credit(
        [
            {
                "name": "Credited Artist",
                "artist": {"name": "Canonical Artist"},
                "joinphrase": " feat. ",
            },
            {
                "name": "Guest Alias",
                "artist": {"name": "Canonical Guest"},
                "joinphrase": "",
            },
        ]
    )

    assert artist == "Credited Artist feat. Guest Alias"
