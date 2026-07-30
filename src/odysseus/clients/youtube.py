"""
YouTube Client Module
A client for searching YouTube videos and extracting video information.
"""

import urllib.parse
import json
from typing import Optional, List, Dict, Any
from ..models.search_results import YouTubeVideo
from ..core.config import YOUTUBE_CONFIG, ERROR_MESSAGES


class YouTubeClient:
    """YouTube search and video information client."""

    def __init__(
        self,
        search_terms: str,
        max_results: Optional[int] = None,
        http_client=None,
    ) -> None:
        self.search_terms = search_terms
        self.max_results = max_results or YOUTUBE_CONFIG["MAX_RESULTS"]
        self.base_url = YOUTUBE_CONFIG["BASE_URL"]
        self.user_agent = YOUTUBE_CONFIG["USER_AGENT"]
        self.max_retries = YOUTUBE_CONFIG["MAX_RETRIES"]
        self.timeout = YOUTUBE_CONFIG["TIMEOUT"]
        self.api_key = YOUTUBE_CONFIG.get("API_KEY", "")
        self.api_base_url = YOUTUBE_CONFIG.get(
            "API_BASE_URL",
            "https://www.googleapis.com/youtube/v3",
        )
        if http_client is None:
            from ..core.http import HttpClient
            http_client = HttpClient(
                default_timeout=self.timeout,
                default_request_delay=0.5,
            )
        self.http_client = http_client
        self.request_delay = 0.5
        if hasattr(self.http_client, "set_session_request_delay"):
            self.http_client.set_session_request_delay("youtube-api", self.request_delay)
            self.http_client.set_session_request_delay("youtube-web", self.request_delay)

        self.headers = {"User-Agent": self.user_agent}
        self.videos: List[YouTubeVideo] = self._search()

    def _extract_json_from_html(self, html: str, json_key: str) -> Dict[str, Any]:
        """Extract JSON object from HTML by key (e.g., 'ytInitialData', 'ytInitialPlayerResponse')."""
        try:
            start = html.index(json_key) + len(json_key) + 3
            end = html.index("};", start) + 1
            json_str = html[start:end]
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            raise Exception(f"Error parsing {json_key} from HTML.") from e

    def _search(self) -> List[YouTubeVideo]:
        if self.api_key:
            api_results = self._search_api()
            if api_results:
                return api_results
        return self._search_html()

    def _search_api(self) -> List[YouTubeVideo]:
        """Use the supported YouTube Data API when a key is configured."""
        data = self.http_client.get_json(
            f"{self.api_base_url}/search",
            params={
                "part": "snippet",
                "q": self.search_terms,
                "type": "video",
                "maxResults": min(max(1, self.max_results), 50),
                "key": self.api_key,
            },
            timeout=self.timeout,
            handle_rate_limit=True,
            rate_limit_codes=(429,),
            rate_limit_wait=60,
            session_name="youtube-api",
            headers={"Accept": "application/json"},
        )
        if not data:
            return []

        results: List[YouTubeVideo] = []
        for item in data.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if not video_id:
                continue
            results.append(
                YouTubeVideo(
                    title=snippet.get("title") or "Unknown",
                    artist=snippet.get("channelTitle") or "Unknown Artist",
                    video_id=video_id,
                    channel=snippet.get("channelTitle"),
                    publish_time=snippet.get("publishedAt"),
                    url_suffix=f"/watch?v={video_id}",
                )
            )
        return results[: self.max_results]

    def _search_html(self) -> List[YouTubeVideo]:
        """Fallback for installations without a YouTube Data API key."""
        encoded_search = urllib.parse.quote_plus(self.search_terms)
        url = f"{self.base_url}/results?search_query={encoded_search}"

        # Try a few times to get a valid response containing "ytInitialData"
        for attempt in range(self.max_retries):
            response = self.http_client.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                max_retries=1,
                handle_rate_limit=True,
                rate_limit_codes=(429,),
                rate_limit_wait=30,
                session_name="youtube-web",
            )
            if response is None:
                continue
            html = response.text
            if "ytInitialData" in html:
                try:
                    results = self._parse_html(html)
                    if self.max_results is not None:
                        return results[: self.max_results]
                    return results
                except Exception:
                    continue
        raise Exception(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to retrieve valid YouTube search data.")

    def _parse_html(self, html: str) -> List[YouTubeVideo]:
        results: List[YouTubeVideo] = []
        try:
            data = self._extract_json_from_html(html, "ytInitialData")

            # Traverse the JSON structure to extract video items
            contents = data["contents"]["twoColumnSearchResultsRenderer"][
                "primaryContents"
            ]["sectionListRenderer"]["contents"]
        except (KeyError, Exception) as e:
            raise Exception("Unexpected data format from YouTube.") from e

        for section in contents:
            item_section = section.get("itemSectionRenderer", {})
            for item in item_section.get("contents", []):
                if "videoRenderer" in item:
                    video_data = item["videoRenderer"]
                    title = video_data.get("title", {}).get("runs", [{}])[0].get("text") or "Unknown"
                    channel = video_data.get("longBylineText", {}).get("runs", [{}])[0].get("text") or "Unknown Artist"
                    video_info: YouTubeVideo = YouTubeVideo(
                        title=title,
                        artist=channel,
                        video_id=video_data.get("videoId"),
                        channel=channel,
                        duration=video_data.get("lengthText", {}).get("simpleText"),
                        views=video_data.get("viewCountText", {}).get("simpleText"),
                        publish_time=video_data.get("publishedTimeText", {}).get("simpleText"),
                        url_suffix=video_data.get("navigationEndpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url"),
                    )
                    results.append(video_info)
            # Return as soon as we have parsed one section with videoRenderer entries.
            if results:
                return results
        return results

    def to_list(self, clear_cache: bool = True) -> List[YouTubeVideo]:
        return self.videos

    def get_video_info(self, video_url: str) -> YouTubeVideo:
        """
        Retrieves detailed information for a specific YouTube video.
        The method fetches the video's page and extracts the embedded JSON (ytInitialPlayerResponse)
        which contains video details.

        Args:
        video_url (str): partial URL of the YouTube video.
        e.g. "https://www.youtube.com/watch?v=H0DKiFY90w4"

        Returns:
        YouTubeVideo: A YouTubeVideo object containing video details such as title, author, view count,
        duration, description, keywords, thumbnail(s), upload date, and category.
        """
        video_url = f"{self.base_url}/{video_url}"

        response = self.http_client.get(
            video_url,
            headers=self.headers,
            timeout=self.timeout,
            handle_rate_limit=True,
            session_name="youtube-web",
        )
        if response is None:
            raise Exception("Error fetching video page")

        html = response.text

        try:
            data = self._extract_json_from_html(html, "ytInitialPlayerResponse")
            video_details = data.get("videoDetails", {})
        except (AttributeError, Exception) as e:
            raise Exception("Unexpected data format from YouTube video page.") from e

        title = video_details.get("title") or "Unknown"
        channel = video_details.get("author") or "Unknown Artist"
        video_info: YouTubeVideo = YouTubeVideo(
            title=title,
            artist=channel,
            video_id=video_details.get("videoId"),
            channel=channel,
            duration=video_details.get("lengthSeconds"),
            views=video_details.get("viewCount"),
            publish_time=video_details.get("publishDate"),
            url_suffix=video_details.get("url_suffix"),
        )
        return video_info
