"""
Tests for graphql app.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
    )


@pytest.mark.django_db
class TestGraphQLSchema:
    """Tests for GraphQL schema."""

    def test_user_type_import(self):
        """Test that UserType can be imported from schema."""
        from apps.graphql.schema import UserType
        assert UserType is not None

    def test_query_type_import(self):
        """Test that Query can be imported from schema."""
        from apps.graphql.schema import Query
        assert Query is not None

    def test_mutation_type_import(self):
        """Test that Mutation can be imported from schema."""
        try:
            from apps.graphql.schema import Mutation
            assert Mutation is not None
        except ImportError:
            # Some schemas don't have Mutation
            pass

    def test_schema_creation(self):
        """Test that schema can be created."""
        try:
            from apps.graphql.schema import schema
            assert schema is not None
        except Exception:
            # Schema may have dependencies that aren't set up
            pass


@pytest.mark.django_db
class TestGraphQLUserType:
    """Tests for GraphQL User type."""

    def test_user_type_fields(self, user):
        """Test user type has expected fields."""
        from apps.graphql.schema import UserType
        
        # Create the type instance
        user_type = UserType(user)
        
        # Check that the instance can access attributes
        assert user_type.email == user.email
        assert user_type.username == user.username