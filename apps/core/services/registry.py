"""
Service Registry for CampusHub.

Provides lightweight dependency injection and service lookup for service-layer
classes, factories, and aliases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Type

ServiceKey = str | Type[Any]


@dataclass
class ServiceRegistration:
    """Service registration info."""

    name: str
    service_class: Type[Any] | None = None
    factory: Callable | None = None
    singleton: bool = True
    instance: Any = None
    aliases: set[str] = field(default_factory=set)


class ServiceRegistry:
    """
    Central service registry for dependency injection.
    
    Usage:
        # Register a service
        ServiceRegistry.register(UserService)
        
        # Get service instance
        user_service = ServiceRegistry.get(UserService)
    """
    
    _services: dict[str, ServiceRegistration] = {}

    @classmethod
    def _normalize_name(cls, value: ServiceKey) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, type):
            return value.__name__
        raise TypeError("Service key must be a service name or class")

    @classmethod
    def _bind_aliases(cls, registration: ServiceRegistration):
        for alias in registration.aliases:
            cls._services[alias] = registration

    @classmethod
    def _build_registration(
        cls,
        *,
        primary_name: str,
        service_class: Type[Any] | None = None,
        factory: Callable | None = None,
        singleton: bool = True,
        aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> ServiceRegistration:
        alias_set = {primary_name, *(aliases or [])}
        if service_class is not None:
            alias_set.add(service_class.__name__)

        return ServiceRegistration(
            name=primary_name,
            service_class=service_class,
            factory=factory,
            singleton=singleton,
            aliases=alias_set,
        )

    @classmethod
    def register(
        cls,
        service_class: Type[Any] | None = None,
        *,
        name: str | None = None,
        singleton: bool = True,
        aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    ):
        """
        Register a service class.

        Supports both decorator and direct-call styles:

            @ServiceRegistry.register(name="Users")
            class UserService: ...

            ServiceRegistry.register(UserService, aliases=["users"])
        """

        def decorator(target_class: Type[Any]):
            registration = cls._build_registration(
                primary_name=name or target_class.__name__,
                service_class=target_class,
                singleton=singleton,
                aliases=aliases,
            )
            cls._bind_aliases(registration)
            return target_class

        if service_class is not None:
            return decorator(service_class)
        return decorator

    @classmethod
    def register_factory(
        cls,
        name: str,
        factory: Callable,
        singleton: bool = True,
        aliases: list[str] | tuple[str, ...] | set[str] | None = None,
    ):
        """Register a service factory."""
        registration = cls._build_registration(
            primary_name=name,
            factory=factory,
            singleton=singleton,
        )
        registration.aliases.update(aliases or [])
        cls._bind_aliases(registration)

    @classmethod
    def get(cls, name: ServiceKey) -> Any:
        """Get service instance."""
        normalized_name = cls._normalize_name(name)
        if normalized_name not in cls._services:
            raise KeyError(f"Service '{normalized_name}' not registered")

        registration = cls._services[normalized_name]

        # Use factory if provided
        if registration.factory:
            if registration.singleton:
                if registration.instance is None:
                    registration.instance = registration.factory()
                return registration.instance
            return registration.factory()
        
        # Use singleton
        if registration.singleton:
            if registration.instance is None:
                registration.instance = registration.service_class()
            return registration.instance
        
        if registration.service_class is None:
            raise KeyError(f"Service '{registration.name}' does not have a class binding")

        return registration.service_class()

    @classmethod
    def get_service_class(cls, name: ServiceKey) -> Type[Any]:
        """Get service class."""
        normalized_name = cls._normalize_name(name)
        if normalized_name not in cls._services:
            raise KeyError(f"Service '{normalized_name}' not registered")

        service_class = cls._services[normalized_name].service_class
        if service_class is None:
            raise KeyError(f"Service '{normalized_name}' is registered via factory only")
        return service_class

    @classmethod
    def has_service(cls, name: ServiceKey) -> bool:
        """Check if service is registered."""
        return cls._normalize_name(name) in cls._services

    @classmethod
    def list_services(cls) -> list[str]:
        """List all registered services."""
        return sorted({registration.name for registration in cls._services.values()})

    @classmethod
    def unregister(cls, name: ServiceKey):
        """Remove a service registration and all of its aliases."""
        normalized_name = cls._normalize_name(name)
        if normalized_name not in cls._services:
            return

        registration = cls._services[normalized_name]
        for alias in list(registration.aliases):
            cls._services.pop(alias, None)

    @classmethod
    def clear(cls):
        """Clear all registrations (for testing)."""
        cls._services.clear()

    @classmethod
    def reset_instances(cls):
        """Reset all singleton instances."""
        seen: set[int] = set()
        for registration in cls._services.values():
            registration_id = id(registration)
            if registration_id in seen:
                continue
            seen.add(registration_id)
            registration.instance = None


def get_service(name: ServiceKey) -> Any:
    """Get service by name."""
    return ServiceRegistry.get(name)


# Service interfaces for type hints
class IService:
    """Base interface for services."""
    pass
