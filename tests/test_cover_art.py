"""Tests for cover art fetching and payload validation."""

import base64
from unittest.mock import MagicMock, patch

from mutagen.flac import Picture
from mutagen.mp4 import MP4Cover

from odysseus.domain.media.cover_art.fetcher import CoverArtFetcher

def test_existing_m4a_cover_is_extracted_as_bytes(tmp_path):
    audio_file = tmp_path / "track.m4a"
    audio_file.touch()
    cover_data = b"\xff\xd8\xffimage"
    audio = MagicMock()
    audio.tags = {
        "covr": [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
    }
    fetcher = CoverArtFetcher.__new__(CoverArtFetcher)

    with patch("mutagen.mp4.MP4", return_value=audio):
        extracted = fetcher._extract_cover_art_from_folder(tmp_path)

    assert extracted == cover_data

def test_existing_opus_cover_is_considered_for_fallback(tmp_path):
    audio_file = tmp_path / "track.opus"
    audio_file.touch()
    cover_data = b"\x89PNG\r\n\x1a\nimage"
    picture = Picture()
    picture.data = cover_data
    picture.type = 3
    picture.mime = "image/png"
    audio = MagicMock()
    audio.tags = {
        "metadata_block_picture": [
            base64.b64encode(picture.write()).decode("ascii")
        ]
    }
    fetcher = CoverArtFetcher.__new__(CoverArtFetcher)

    with patch("mutagen.File", return_value=audio):
        extracted = fetcher._extract_cover_art_from_folder(tmp_path)

    assert extracted == cover_data

def test_cover_art_rejects_non_image_http_200():
    fetcher = CoverArtFetcher(http_client=MagicMock(), cache_manager=None)
    response = MagicMock()
    response.status_code = 200
    response.content = b"<html>cdn error</html>"
    fetcher.http_client.get.return_value = response

    result = fetcher.fetch_cover_art_from_url("https://cdn.test/cover.jpg")

    assert result is None
    assert not fetcher.cover_art_cache.has("https://cdn.test/cover.jpg")

def test_cover_art_accepts_jpeg_magic_bytes():
    assert CoverArtFetcher._is_image_payload(b"\xff\xd8\xff" + b"\x00" * 20)
    assert CoverArtFetcher._is_image_payload(
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    )
    assert not CoverArtFetcher._is_image_payload(b"{'error': true}")
