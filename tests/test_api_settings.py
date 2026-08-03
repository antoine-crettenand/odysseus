"""Tests for secure GUI provider settings and live credential updates."""

import pytest

from odysseus.application.api_settings import ApiSettingsService, CredentialStore


class StoreStub:
    def __init__(self, persistent=True):
        self.values = {}
        self.persistent = persistent

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.values.pop(key, None)


class DiscogsStub:
    def __init__(self):
        self.tokens = []

    def set_user_token(self, value):
        self.tokens.append(value)


class SpotifyStub:
    def __init__(self):
        self.credentials = []

    def set_credentials(self, client_id, client_secret):
        self.credentials.append((client_id, client_secret))


class AppleMusicStub:
    def __init__(self):
        self.credentials = []

    def set_credentials(self, token, storefront):
        self.credentials.append((token, storefront))


class AcoustIDStub:
    def __init__(self):
        self.keys = []

    def set_api_key(self, value):
        self.keys.append(value)


def make_service(store=None):
    youtube_config = {"API_KEY": ""}
    clients = {
        "discogs_client": DiscogsStub(),
        "spotify_client": SpotifyStub(),
        "apple_music_client": AppleMusicStub(),
        "acoustid_client": AcoustIDStub(),
    }
    service = ApiSettingsService(
        youtube_config=youtube_config,
        credential_store=store or StoreStub(),
        **clients,
    )
    return service, youtube_config, clients


def test_api_settings_save_applies_credentials_without_exposing_them():
    store = StoreStub()
    service, youtube, clients = make_service(store)

    service.save(
        {
            "youtube_api_key": "youtube-secret",
            "discogs_user_token": "discogs-secret",
            "spotify_client_id": "spotify-id",
            "spotify_client_secret": "spotify-secret",
            "apple_music_developer_token": "apple-secret",
            "apple_music_storefront": "CH",
            "acoustid_api_key": "acoustid-secret",
        }
    )

    assert youtube["API_KEY"] == "youtube-secret"
    assert clients["discogs_client"].tokens[-1] == "discogs-secret"
    assert clients["spotify_client"].credentials[-1] == (
        "spotify-id",
        "spotify-secret",
    )
    assert clients["apple_music_client"].credentials[-1] == (
        "apple-secret",
        "ch",
    )
    assert clients["acoustid_client"].keys[-1] == "acoustid-secret"

    summary = service.summary()
    assert summary == {
        "youtubeConfigured": True,
        "discogsConfigured": True,
        "spotifyConfigured": True,
        "appleMusicConfigured": True,
        "acoustidConfigured": True,
        "storefront": "ch",
        "storageLabel": "System keychain",
        "persistentStorage": True,
    }
    assert "secret" not in repr(summary)


def test_blank_fields_preserve_existing_saved_secrets():
    store = StoreStub()
    store.values["discogs_user_token"] = "existing-token"
    service, _, clients = make_service(store)

    service.save({"discogs_user_token": "", "apple_music_storefront": "us"})

    assert store.values["discogs_user_token"] == "existing-token"
    assert clients["discogs_client"].tokens[-1] == "existing-token"


def test_clear_provider_removes_saved_values_and_live_credentials():
    store = StoreStub()
    store.values.update(
        {
            "spotify_client_id": "id",
            "spotify_client_secret": "secret",
        }
    )
    service, _, clients = make_service(store)

    service.clear_provider("spotify")

    assert "spotify_client_id" not in store.values
    assert "spotify_client_secret" not in store.values
    assert clients["spotify_client"].credentials[-1] == ("", "")
    assert service.summary()["spotifyConfigured"] is False


def test_storefront_validation_rejects_invalid_values():
    service, _, _ = make_service()

    with pytest.raises(ValueError, match="two-letter country code"):
        service.save({"apple_music_storefront": "switzerland"})


def test_environment_credentials_are_applied_when_keychain_is_empty(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "environment-key")
    service, youtube, _ = make_service(StoreStub())

    assert youtube["API_KEY"] == "environment-key"
    assert service.summary()["youtubeConfigured"] is True


class FailingKeyringBackend:
    priority = 1

    def get_password(self, service, key):
        raise RuntimeError("keychain unavailable")

    def set_password(self, service, key, value):
        raise RuntimeError("keychain unavailable")

    def delete_password(self, service, key):
        raise RuntimeError("keychain unavailable")


def test_credential_store_falls_back_to_current_session():
    store = CredentialStore(backend=FailingKeyringBackend())

    store.set("token", "value")

    assert store.get("token") == "value"
    assert store.persistent is False
