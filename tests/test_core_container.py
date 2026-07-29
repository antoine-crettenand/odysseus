"""
Tests for dependency injection container.
"""

import pytest
from unittest.mock import MagicMock
from odysseus.core.container.container import Container, get_container, reset_container
from odysseus.core.container.registration import register_all_services


class TestContainer:
    """Tests for Container class."""

    def test_container_initialization(self):
        """Test container initialization."""
        container = Container()
        assert container._services == {}
        assert container._factories == {}
        assert container._singletons == {}

    def test_register_factory(self):
        """Test registering a factory function."""
        container = Container()
        factory = MagicMock(return_value="service_instance")

        container.register("test_service", factory, singleton=True)

        assert "test_service" in container._factories
        assert container._singletons["test_service"] is True

    def test_replacing_factory_invalidates_cached_singleton(self):
        """A replacement factory must not leave the old singleton active."""
        container = Container()
        container.register("test_service", lambda: "old")
        assert container.get("test_service") == "old"

        container.register("test_service", lambda: "new")

        assert container.get("test_service") == "new"

    def test_register_instance_replaces_factory(self):
        """A direct instance should completely replace an existing factory."""
        container = Container()
        container.register("test_service", lambda: "factory")

        container.register_instance("test_service", "instance")

        assert "test_service" not in container._factories
        assert container.get("test_service") == "instance"

    def test_get_service_singleton(self):
        """Test getting a singleton service."""
        container = Container()
        factory = MagicMock(return_value="service_instance")

        container.register("test_service", factory, singleton=True)

        instance1 = container.get("test_service")
        instance2 = container.get("test_service")

        assert instance1 == "service_instance"
        assert instance2 == "service_instance"
        assert instance1 is instance2
        assert factory.call_count == 1

    def test_get_service_non_singleton(self):
        """Test getting a non-singleton service."""
        container = Container()
        factory = MagicMock(return_value="service_instance")

        container.register("test_service", factory, singleton=False)

        instance1 = container.get("test_service")
        instance2 = container.get("test_service")

        assert instance1 == "service_instance"
        assert instance2 == "service_instance"
        assert factory.call_count == 2

    def test_get_unregistered_service(self):
        """Test getting an unregistered service raises ValueError."""
        container = Container()

        with pytest.raises(ValueError, match="Service 'unknown' not registered"):
            container.get("unknown")

    def test_register_instance(self):
        """Test registering a service instance directly."""
        container = Container()
        instance = MagicMock()

        container.register_instance("test_service", instance)

        assert container.get("test_service") is instance
        assert container._services["test_service"] is instance

    def test_has_service(self):
        """Test checking if a service is registered."""
        container = Container()

        assert container.has("test_service") is False

        container.register("test_service", lambda: "instance")
        assert container.has("test_service") is True

        container.register_instance("test_instance", "value")
        assert container.has("test_instance") is True

    def test_clear_container(self):
        """Test clearing all services."""
        container = Container()
        container.register("test_service", lambda: "instance")
        container.register_instance("test_instance", "value")

        container.clear()

        assert container._services == {}
        assert container._factories == {}
        assert container._singletons == {}


class TestGlobalContainer:
    """Tests for global container functions."""

    def test_get_container_returns_singleton(self):
        """Test that get_container returns the same instance."""
        reset_container()
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_reset_container(self):
        """Test resetting the global container."""
        container1 = get_container()
        container1.register("test", lambda: "value")

        reset_container()
        container2 = get_container()

        assert container1 is not container2
        assert not container2.has("test")


def test_registered_search_service_uses_youtube_client_factory():
    """The DI graph should expose a callable factory, not instantiate a query client."""
    container = Container()
    register_all_services(container)

    search_service = container.get("search_service")
    youtube_client_factory = container.get("youtube_client_factory")

    assert callable(youtube_client_factory)
    assert search_service.youtube_client_factory is youtube_client_factory
