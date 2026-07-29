"""
Dependency injection container for Odysseus.
"""
from typing import Dict, TypeVar, Callable, Any, Optional
T = TypeVar('T')


class Container:
    """Simple dependency injection container."""

    def __init__(self):
        """Initialize the container."""
        self._services: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._singletons: Dict[str, bool] = {}

    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        singleton: bool = True
    ) -> None:
        """
        Register a service factory.

        Args:
            name: Service name
            factory: Factory function that creates the service
            singleton: Whether to cache the instance (default: True)
        """
        self._services.pop(name, None)
        self._factories[name] = factory
        self._singletons[name] = singleton

    def get(self, name: str) -> Any:
        """
        Get a service instance.

        Args:
            name: Service name

        Returns:
            Service instance

        Raises:
            ValueError: If service is not registered
        """
        # Check if already instantiated (for singletons)
        if name in self._services:
            return self._services[name]

        if name not in self._factories:
            raise ValueError(f"Service '{name}' not registered")

        # Create instance
        instance = self._factories[name]()

        # Cache if singleton
        if self._singletons.get(name, True):
            self._services[name] = instance

        return instance

    def register_instance(self, name: str, instance: Any) -> None:
        """
        Register a service instance directly.

        Args:
            name: Service name
            instance: Service instance
        """
        self._factories.pop(name, None)
        self._services[name] = instance
        self._singletons[name] = True

    def has(self, name: str) -> bool:
        """
        Check if a service is registered.

        Args:
            name: Service name

        Returns:
            True if service is registered
        """
        return name in self._factories or name in self._services

    def clear(self) -> None:
        """Clear all registered services and factories."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """
    Get the global container instance.

    Returns:
        Global container instance
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    _container = None
