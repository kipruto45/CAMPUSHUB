"""Tests for the core service registry and base service helpers."""

import pytest
from django.contrib.auth import get_user_model

from apps.core.services.base import ServiceContext, ServiceResult, WriteService
from apps.core.services.registry import ServiceRegistry, get_service

User = get_user_model()


class ExampleService:
    def __init__(self):
        self.token = object()


class ExampleNonSingletonService:
    def __init__(self):
        self.token = object()


class ExampleUserWriteService(WriteService[User]):
    model_class = User

    def validate(self, data: dict, partial: bool = False) -> bool:
        self._validation_errors = []
        if not partial and not data.get("email"):
            self._add_validation_error("email", "Email is required", code="required")
        return not self._validation_errors


@pytest.mark.django_db
class TestBaseServices:
    def test_service_result_helpers(self):
        ok = ServiceResult.ok(data={"value": 1}, warnings=["cached"])
        failure = ServiceResult.error("boom")

        assert ok.is_ok is True
        assert ok.data == {"value": 1}
        assert ok.warnings == ["cached"]
        assert failure.is_error is True
        assert failure.error == "boom"

    def test_service_context_properties(self, user, rf):
        context = ServiceContext(user=user, request=rf.get("/"), source="tests")

        assert context.is_authenticated is True
        assert context.is_admin is False
        assert context.get("source") == "tests"

    def test_write_service_commit_false_returns_unsaved_instance(self):
        service = ExampleUserWriteService()

        result = service.create(
            {
                "email": "unsaved@example.com",
                "full_name": "Unsaved User",
            },
            commit=False,
        )

        assert result.is_ok is True
        assert result.data.pk is None
        assert User.objects.filter(email="unsaved@example.com").exists() is False

    def test_write_service_validation_error(self):
        service = ExampleUserWriteService()

        result = service.create({"full_name": "Missing Email"})

        assert result.is_error is True
        assert result.error == "Validation failed"
        assert result.errors == [
            {"field": "email", "message": "Email is required", "code": "required"}
        ]

    def test_write_service_update_and_delete(self):
        service = ExampleUserWriteService()
        user = User.objects.create(email="registry-update@example.com")

        update_result = service.update(user, {"full_name": "Updated Name"})
        user.refresh_from_db()

        assert update_result.is_ok is True
        assert user.full_name == "Updated Name"

        delete_result = service.delete(user)
        assert delete_result.is_ok is True
        assert User.objects.filter(email="registry-update@example.com").exists() is False


class TestServiceRegistry:
    def setup_method(self):
        ServiceRegistry.clear()

    def teardown_method(self):
        ServiceRegistry.clear()

    def test_register_direct_and_resolve_by_class_or_name(self):
        ServiceRegistry.register(ExampleService, aliases=["example", "example-service"])

        by_class = ServiceRegistry.get(ExampleService)
        by_name = ServiceRegistry.get("example")
        by_alias = get_service("example-service")

        assert by_class is by_name is by_alias
        assert ServiceRegistry.has_service(ExampleService) is True
        assert ServiceRegistry.get_service_class("example") is ExampleService

    def test_register_decorator_and_non_singleton_factory(self):
        @ServiceRegistry.register(name="decorated-service")
        class DecoratedService:
            pass

        ServiceRegistry.register_factory(
            "ephemeral",
            factory=ExampleNonSingletonService,
            singleton=False,
            aliases=["ephemeral-alias"],
        )

        decorated_a = ServiceRegistry.get("decorated-service")
        decorated_b = ServiceRegistry.get(DecoratedService)
        transient_a = ServiceRegistry.get("ephemeral")
        transient_b = ServiceRegistry.get("ephemeral-alias")

        assert decorated_a is decorated_b
        assert transient_a is not transient_b

    def test_list_unregister_and_reset_instances(self):
        ServiceRegistry.register(ExampleService, aliases=["example"])
        ServiceRegistry.register_factory("factory-service", factory=ExampleService)

        names = ServiceRegistry.list_services()
        assert names == ["ExampleService", "factory-service"]

        first = ServiceRegistry.get("ExampleService")
        ServiceRegistry.reset_instances()
        second = ServiceRegistry.get("example")
        assert first is not second

        ServiceRegistry.unregister("example")
        assert ServiceRegistry.has_service("ExampleService") is False

    def test_factory_only_service_class_lookup_raises(self):
        ServiceRegistry.register_factory("factory-only", factory=ExampleService)

        with pytest.raises(KeyError):
            ServiceRegistry.get_service_class("factory-only")
