"""API settings and validation constants for the desktop controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.config import VALIDATION_RULES

if TYPE_CHECKING:
    from .controller import OdysseusController


class SettingsBridge:
    """Plain helper for provider settings get/save/clear."""

    def __init__(self, host: OdysseusController) -> None:
        self._host = host
        self.message = ""

    @property
    def min_year(self) -> int:
        return int(VALIDATION_RULES["MIN_YEAR"])

    @property
    def max_year(self) -> int:
        return int(VALIDATION_RULES["MAX_YEAR"])

    def summary(self) -> dict:
        service = self._host.settings_service
        if service is None:
            return {
                "youtubeConfigured": False,
                "discogsConfigured": False,
                "spotifyConfigured": False,
                "appleMusicConfigured": False,
                "acoustidConfigured": False,
                "storefront": "us",
                "storageLabel": "Unavailable",
                "persistentStorage": False,
            }
        return service.summary()

    def save(self, updates: dict) -> bool:
        service = self._host.settings_service
        if service is None:
            self.message = "API settings are unavailable."
            self._host.settingsChanged.emit()
            return False
        try:
            service.save(dict(updates))
        except Exception as error:
            self.message = str(error) or "Could not save API settings."
            self._host.settingsChanged.emit()
            return False
        self.message = "Provider settings saved and applied."
        self._host.settingsChanged.emit()
        return True

    def clear_provider(self, provider: str) -> bool:
        service = self._host.settings_service
        if service is None:
            self.message = "API settings are unavailable."
            self._host.settingsChanged.emit()
            return False
        try:
            service.clear_provider(provider)
        except Exception as error:
            self.message = str(error) or "Could not clear credentials."
            self._host.settingsChanged.emit()
            return False
        self.message = f"Cleared saved {provider} settings."
        self._host.settingsChanged.emit()
        return True
