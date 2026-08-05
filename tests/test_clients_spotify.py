"""
Tests for Spotify client.
"""

from unittest.mock import patch, MagicMock, Mock
from odysseus.clients.spotify import SpotifyClient


class TestSpotifyClient:
    """Tests for SpotifyClient class."""

    def test_spotify_client_initialization(self):
        """Test SpotifyClient initialization."""
        with patch.dict("os.environ", {}, clear=True):
            client = SpotifyClient()

            assert client.base_url == "https://api.spotify.com/v1"
            assert client.auth_url == "https://accounts.spotify.com/api/token"
            assert client.client_id is None
            assert client.client_secret is None
            assert client.access_token is None
            assert client.timeout == 30

    def test_spotify_client_with_credentials(self):
        """Test SpotifyClient initialization with credentials."""
        with patch.dict("os.environ", {
            "SPOTIFY_CLIENT_ID": "test_id",
            "SPOTIFY_CLIENT_SECRET": "test_secret"
        }):
            with patch.object(SpotifyClient, "_authenticate", return_value=True):
                client = SpotifyClient()

                assert client.client_id == "test_id"
                assert client.client_secret == "test_secret"

    def test_parse_spotify_url_playlist(self):
        """Test parsing Spotify playlist URL."""
        client = SpotifyClient()

        url = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
        result = client.parse_spotify_url(url)

        assert result is not None
        assert result["type"] == "playlist"
        assert result["id"] == "37i9dQZF1DXcBWIGoYBM5M"

    def test_parse_spotify_url_album(self):
        """Test parsing Spotify album URL."""
        client = SpotifyClient()

        url = "https://open.spotify.com/album/4uLU6hMCjMI75M1n2eNuSF"
        result = client.parse_spotify_url(url)

        assert result is not None
        assert result["type"] == "album"
        assert result["id"] == "4uLU6hMCjMI75M1n2eNuSF"

    def test_parse_spotify_url_track(self):
        """Test parsing Spotify track URL."""
        client = SpotifyClient()

        url = "https://open.spotify.com/track/4uLU6hMCjMI75M1n2eNuSF"
        result = client.parse_spotify_url(url)

        assert result is not None
        assert result["type"] == "track"
        assert result["id"] == "4uLU6hMCjMI75M1n2eNuSF"

    def test_parse_spotify_url_uri_format(self):
        """Test parsing Spotify URI format."""
        client = SpotifyClient()

        url = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
        result = client.parse_spotify_url(url)

        assert result is not None
        assert result["type"] == "playlist"
        assert result["id"] == "37i9dQZF1DXcBWIGoYBM5M"

    def test_parse_spotify_url_invalid(self):
        """Test parsing invalid Spotify URL."""
        client = SpotifyClient()

        result = client.parse_spotify_url("https://example.com")
        assert result is None

        result = client.parse_spotify_url("")
        assert result is None

        result = client.parse_spotify_url(None)
        assert result is None

    def test_parse_spotify_url_with_locale(self):
        """Test parsing Spotify URL with locale prefix."""
        client = SpotifyClient()

        url = "https://open.spotify.com/intl-fr/playlist/37i9dQZF1DXcBWIGoYBM5M"
        result = client.parse_spotify_url(url)

        assert result is not None
        assert result["type"] == "playlist"
        assert result["id"] == "37i9dQZF1DXcBWIGoYBM5M"

    def test_get_headers_without_token(self):
        """Test getting headers without access token."""
        client = SpotifyClient()
        headers = client._get_headers()

        assert headers == {"Content-Type": "application/json"}
        assert "Authorization" not in headers

    def test_get_headers_with_token(self):
        """Test getting headers with access token."""
        client = SpotifyClient()
        client.access_token = "test_token"
        headers = client._get_headers()

        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test_token"

    @patch("requests.post")
    def test_authenticate_success(self, mock_post):
        """Test successful authentication."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "test_token"}
        mock_post.return_value = mock_response

        client = SpotifyClient()
        client.client_id = "test_id"
        client.client_secret = "test_secret"

        result = client._authenticate()

        assert result is True
        assert client.access_token == "test_token"
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_authenticate_failure(self, mock_post):
        """Test failed authentication."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        client = SpotifyClient()
        client.client_id = "test_id"
        client.client_secret = "test_secret"

        result = client._authenticate()

        assert result is False
        assert client.access_token is None

    @patch("requests.post")
    def test_authenticate_exception(self, mock_post):
        """Test authentication with exception."""
        mock_post.side_effect = Exception("Network error")

        client = SpotifyClient()
        client.client_id = "test_id"
        client.client_secret = "test_secret"

        result = client._authenticate()

        assert result is False

    def test_authenticate_no_credentials(self):
        """Test authentication without credentials."""
        client = SpotifyClient()
        client.client_id = None
        client.client_secret = None

        result = client._authenticate()

        assert result is False

    def test_request_refreshes_expired_token_once(self):
        unauthorized = Mock(status_code=401)
        success = Mock(status_code=200)
        success.json.return_value = {"albums": {"items": []}}
        http_client = MagicMock()
        http_client.get.side_effect = [unauthorized, success]
        client = SpotifyClient(http_client=http_client)
        client.client_id = "test_id"
        client.client_secret = "test_secret"

        with patch.object(
            client,
            "_authenticate",
            side_effect=lambda: (
                setattr(client, "access_token", "refreshed") or True
            ),
        ) as authenticate:
            result = client._request_json("https://api.spotify.test/search")

        assert result == {"albums": {"items": []}}
        authenticate.assert_called_once()
        assert http_client.get.call_count == 2

    def test_search_items_uses_shared_resilient_transport(self):
        http_client = MagicMock()
        response = Mock(status_code=200)
        response.json.return_value = {
            "tracks": {"items": [{"id": "track-id"}]}
        }
        http_client.get.return_value = response
        client = SpotifyClient(http_client=http_client)
        client.access_token = "token"

        result = client.search_items("track:test", "track", limit=5)

        assert result == [{"id": "track-id"}]
        assert http_client.get.call_args.kwargs["session_name"] == "spotify"
        assert http_client.get.call_args.kwargs["handle_rate_limit"] is True
def test_parse_collection_url():
    client = SpotifyClient.__new__(SpotifyClient)

    parsed = client.parse_spotify_url(
        "https://open.spotify.com/user/example/collection"
    )

    assert parsed == {"type": "collection", "id": "example"}
