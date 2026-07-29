"""Tests for resilient YouTube search paths."""

from unittest.mock import MagicMock

from odysseus.clients.youtube import YouTubeClient


def test_official_api_results_are_converted_to_videos():
    client = YouTubeClient.__new__(YouTubeClient)
    client.search_terms = "artist title"
    client.max_results = 3
    client.timeout = 30
    client.api_key = "api-key"
    client.api_base_url = "https://www.googleapis.com/youtube/v3"
    client.http_client = MagicMock()
    client.http_client.get_json.return_value = {
        "items": [
            {
                "id": {"videoId": "video-id"},
                "snippet": {
                    "title": "Title",
                    "channelTitle": "Channel",
                    "publishedAt": "2020-01-01T00:00:00Z",
                },
            }
        ]
    }

    videos = client._search_api()

    assert [video.video_id for video in videos] == ["video-id"]
    assert videos[0].title == "Title"
    assert client.http_client.get_json.call_args.kwargs["session_name"] == (
        "youtube-api"
    )


def test_configured_official_api_is_preferred_over_html_fallback():
    client = YouTubeClient.__new__(YouTubeClient)
    client.api_key = "api-key"
    expected = [MagicMock()]
    client._search_api = MagicMock(return_value=expected)
    client._search_html = MagicMock()

    assert client._search() == expected
    client._search_html.assert_not_called()
