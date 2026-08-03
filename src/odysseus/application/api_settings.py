"""Secure provider credential settings and live client configuration."""

import os
import re
from typing import Dict, Optional

from ..core.config import APPLE_MUSIC_CONFIG, YOUTUBE_CONFIG


class CredentialStore:
    """Store credentials in the OS keychain, with a session-only fallback."""

    service_name = "Odysseus Music Discovery"

    def __init__(self, backend=None) -> None:
        self._memory: Dict[str, str] = {}
        self._backend = backend
        self.persistent = backend is not None
        if backend is None:
            try:
                import keyring

                candidate = keyring.get_keyring()
                if getattr(candidate, "priority", 0) > 0:
                    self._backend = keyring
                    self.persistent = True
            except Exception:
                self._backend = None
                self.persistent = False

    def get(self, key: str) -> Optional[str]:
        if key in self._memory:
            return self._memory[key]
        if self._backend is not None:
            try:
                return self._backend.get_password(self.service_name, key)
            except Exception:
                self.persistent = False
        return None

    def set(self, key: str, value: str) -> None:
        if self._backend is not None:
            try:
                self._backend.set_password(self.service_name, key, value)
                self._memory.pop(key, None)
                return
            except Exception:
                self.persistent = False
        self._memory[key] = value

    def delete(self, key: str) -> None:
        self._memory.pop(key, None)
        if self._backend is not None:
            try:
                self._backend.delete_password(self.service_name, key)
            except Exception:
                # Missing credentials and unavailable keychains are both safe
                # outcomes for a user-requested clear operation.
                pass


class ApiSettingsService:
    """Overlay keychain credentials on environment configuration at runtime."""

    _ENVIRONMENT_KEYS = {
        "youtube_api_key": "YOUTUBE_API_KEY",
        "discogs_user_token": "DISCOGS_USER_TOKEN",
        "spotify_client_id": "SPOTIFY_CLIENT_ID",
        "spotify_client_secret": "SPOTIFY_CLIENT_SECRET",
        "apple_music_developer_token": "APPLE_MUSIC_DEVELOPER_TOKEN",
        "apple_music_storefront": "APPLE_MUSIC_STOREFRONT",
        "acoustid_api_key": "ACOUSTID_API_KEY",
    }
    _PROVIDER_KEYS = {
        "youtube": ("youtube_api_key",),
        "discogs": ("discogs_user_token",),
        "spotify": ("spotify_client_id", "spotify_client_secret"),
        "applemusic": (
            "apple_music_developer_token",
            "apple_music_storefront",
        ),
        "acoustid": ("acoustid_api_key",),
    }

    def __init__(
        self,
        *,
        youtube_config=None,
        discogs_client=None,
        spotify_client=None,
        apple_music_client=None,
        acoustid_client=None,
        credential_store=None,
    ) -> None:
        self.youtube_config = youtube_config or YOUTUBE_CONFIG
        self.discogs_client = discogs_client
        self.spotify_client = spotify_client
        self.apple_music_client = apple_music_client
        self.acoustid_client = acoustid_client
        self.store = credential_store or CredentialStore()
        self.apply()

    def _value(self, key: str, default: str = "") -> str:
        stored = self.store.get(key)
        if stored is not None:
            return stored
        environment_key = self._ENVIRONMENT_KEYS[key]
        return os.getenv(environment_key, default)

    def apply(self) -> None:
        """Apply current settings to already-created provider clients."""
        youtube_key = self._value("youtube_api_key")
        discogs_token = self._value("discogs_user_token")
        spotify_id = self._value("spotify_client_id")
        spotify_secret = self._value("spotify_client_secret")
        apple_token = self._value("apple_music_developer_token")
        storefront = self._value(
            "apple_music_storefront",
            APPLE_MUSIC_CONFIG.get("STOREFRONT", "us"),
        ).lower()
        acoustid_key = self._value("acoustid_api_key")

        self.youtube_config["API_KEY"] = youtube_key
        if self.discogs_client is not None:
            self.discogs_client.set_user_token(discogs_token)
        if self.spotify_client is not None:
            self.spotify_client.set_credentials(spotify_id, spotify_secret)
        if self.apple_music_client is not None:
            self.apple_music_client.set_credentials(apple_token, storefront)
        if self.acoustid_client is not None:
            self.acoustid_client.set_api_key(acoustid_key)

    def summary(self) -> Dict[str, object]:
        """Return configuration state without returning secret values."""
        spotify_id = self._value("spotify_client_id")
        spotify_secret = self._value("spotify_client_secret")
        return {
            "youtubeConfigured": bool(self._value("youtube_api_key")),
            "discogsConfigured": bool(self._value("discogs_user_token")),
            "spotifyConfigured": bool(spotify_id and spotify_secret),
            "appleMusicConfigured": bool(
                self._value("apple_music_developer_token")
            ),
            "acoustidConfigured": bool(self._value("acoustid_api_key")),
            "storefront": self._value(
                "apple_music_storefront",
                APPLE_MUSIC_CONFIG.get("STOREFRONT", "us"),
            ).lower(),
            "storageLabel": (
                "System keychain" if self.store.persistent else "This session only"
            ),
            "persistentStorage": self.store.persistent,
        }

    def save(self, updates: Dict[str, str]) -> None:
        """Persist non-empty updates; blank secret fields mean keep existing."""
        storefront = str(updates.get("apple_music_storefront", "")).strip().lower()
        if storefront and not re.fullmatch(r"[a-z]{2}", storefront):
            raise ValueError("Apple Music storefront must be a two-letter country code")

        for key in self._ENVIRONMENT_KEYS:
            value = str(updates.get(key, "")).strip()
            if value:
                self.store.set(key, value)
        self.apply()

    def clear_provider(self, provider: str) -> None:
        """Remove keychain overrides for one known provider."""
        provider_key = provider.casefold().replace(" ", "")
        if provider_key not in self._PROVIDER_KEYS:
            raise ValueError(f"Unknown API provider: {provider}")
        for key in self._PROVIDER_KEYS[provider_key]:
            self.store.delete(key)
        self.apply()
