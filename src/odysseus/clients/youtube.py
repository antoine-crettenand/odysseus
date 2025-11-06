"""
YouTube Client Module
A client for searching YouTube videos and extracting video information.
"""

import requests
import urllib.parse
import json
import re
from typing import Optional, List, Dict, Any
from ..models.search_results import YouTubeVideo
from ..core.config import YOUTUBE_CONFIG, ERROR_MESSAGES


class YouTubeClient:
    """YouTube search and video information client."""
    
    def __init__(self, search_terms: str, max_results: Optional[int] = None) -> None:
        self.search_terms = search_terms
        self.max_results = max_results or YOUTUBE_CONFIG["MAX_RESULTS"]
        self.base_url = YOUTUBE_CONFIG["BASE_URL"]
        self.user_agent = YOUTUBE_CONFIG["USER_AGENT"]
        self.max_retries = YOUTUBE_CONFIG["MAX_RETRIES"]
        self.timeout = YOUTUBE_CONFIG["TIMEOUT"]
        
        self.headers = {"User-Agent": self.user_agent}
        self.videos: List[YouTubeVideo] = self._search()

    def _search(self) -> List[YouTubeVideo]:
        encoded_search = urllib.parse.quote_plus(self.search_terms)
        url = f"{self.base_url}/results?search_query={encoded_search}"

        # Try a few times to get a valid response containing "ytInitialData"
        for attempt in range(self.max_retries):
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                continue  # Optionally, add a delay here
            html = response.text
            if "ytInitialData" in html:
                results = self._parse_html(html)
                if self.max_results is not None:
                    return results[: self.max_results]
                return results
        # If we exit the loop, we were not able to parse the page.
        raise Exception(f"{ERROR_MESSAGES['NETWORK_ERROR']}: Failed to retrieve valid YouTube search data.")

    def _parse_html(self, html: str) -> List[YouTubeVideo]:
        results: List[YouTubeVideo] = []
        try:
            # Locate the "ytInitialData" JSON object
            start = html.index("ytInitialData") + len("ytInitialData") + 3
            end = html.index("};", start) + 1
            json_str = html[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            raise Exception("Error parsing ytInitialData from HTML.") from e

        # Traverse the JSON structure to extract video items
        try:
            contents = data["contents"]["twoColumnSearchResultsRenderer"][
                "primaryContents"
            ]["sectionListRenderer"]["contents"]
        except KeyError as e:
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

        response = requests.get(video_url, headers=self.headers, timeout=self.timeout)
        if response.status_code != 200:
            raise Exception(f"Error fetching video page, status code: {response.status_code}")
        
        html = response.text
        
        try:
            # Look for ytInitialPlayerResponse in the HTML
            start = html.index("ytInitialPlayerResponse") + len("ytInitialPlayerResponse") + 3
            end = html.index("};", start) + 1
            json_str = html[start:end]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            raise Exception("Error parsing ytInitialPlayerResponse from HTML.") from e

        try:
            video_details = data.get("videoDetails", {})
        except AttributeError:
            raise Exception("Unexpected data format from YouTube video page.")
    
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
