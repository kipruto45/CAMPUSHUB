"""
GraphQL schema for CampusHub.
"""

import graphene
from django.contrib.auth import get_user_model
from graphene_django import DjangoListField, DjangoObjectType

try:
    from apps.resources.models import Resource as ResourceModel
except Exception:  # pragma: no cover - optional app wiring
    ResourceModel = None

try:
    from apps.courses.models import Course as CourseModel
    from apps.courses.models import Unit as UnitModel
except Exception:  # pragma: no cover - optional app wiring
    CourseModel = None
    UnitModel = None

User = get_user_model()


# ============== User Types ==============
class UserType(DjangoObjectType):
    """GraphQL type for User model."""

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "profile_image",
            "bio",
            "course",
            "year_of_study",
            "is_verified",
            "date_joined",
            "last_login",
        )


# ============== Resource Types ==============
if ResourceModel is not None:

    class ResourceType(DjangoObjectType):
        """GraphQL type for Resource model."""

        class Meta:
            model = ResourceModel
            fields = (
                "id",
                "title",
                "description",
                "file",
                "file_type",
                "file_size",
                "thumbnail",
                "course",
                "unit",
                "tags",
                "uploaded_by",
                "download_count",
                "view_count",
                "average_rating",
                "created_at",
                "updated_at",
                "status",
            )

else:

    class ResourceType(graphene.ObjectType):
        """Fallback GraphQL type when Resource model isn't available."""

        id = graphene.ID()
        title = graphene.String()


# ============== Course Types ==============
if CourseModel is not None:

    class CourseType(DjangoObjectType):
        """GraphQL type for Course model."""

        class Meta:
            model = CourseModel
            fields = (
                "id",
                "name",
                "code",
                "description",
                "department",
                "duration_years",
                "created_at",
            )

else:

    class CourseType(graphene.ObjectType):
        """Fallback GraphQL type when Course model isn't available."""

        id = graphene.ID()
        name = graphene.String()


if UnitModel is not None:

    class UnitType(DjangoObjectType):
        """GraphQL type for Unit model."""

        class Meta:
            model = UnitModel
            fields = (
                "id",
                "name",
                "code",
                "description",
                "course",
                "semester",
                "created_at",
            )

else:

    class UnitType(graphene.ObjectType):
        """Fallback GraphQL type when Unit model isn't available."""

        id = graphene.ID()
        name = graphene.String()


# ============== Query Definitions ==============
class Query(graphene.ObjectType):
    """GraphQL queries."""

    # User queries
    me = graphene.Field(UserType)
    user = graphene.Field(UserType, id=graphene.Int(), username=graphene.String())
    users = graphene.List(UserType, limit=graphene.Int())

    # Resource queries
    resource = graphene.Field(ResourceType, id=graphene.Int())
    resources = (
        DjangoListField(ResourceType)
        if ResourceModel is not None
        else graphene.List(ResourceType)
    )
    popular_resources = graphene.List(ResourceType, limit=graphene.Int())
    recent_resources = graphene.List(ResourceType, limit=graphene.Int())

    # Search
    search = graphene.List(
        graphene.NonNull(graphene.String),
        query=graphene.String(required=True),
        limit=graphene.Int(),
    )

    def resolve_me(self, info):
        """Get current user."""
        if not info.context.user.is_authenticated:
            return None
        return info.context.user

    def resolve_user(self, info, id=None, username=None):
        """Get user by ID or username."""
        if id:
            return User.objects.get(pk=id)
        if username:
            return User.objects.get(username=username)
        return None

    def resolve_users(self, info, limit=10):
        """Get list of users."""
        return User.objects.all()[:limit]

    def resolve_resource(self, info, id):
        """Get resource by ID."""
        if ResourceModel is None:
            return None
        from apps.resources.models import Resource

        return Resource.objects.get(pk=id)

    def resolve_resources(self, info):
        """Get all resources."""
        if ResourceModel is None:
            return []
        from apps.resources.models import Resource

        return Resource.objects.filter(status="approved")

    def resolve_popular_resources(self, info, limit=10):
        """Get popular resources."""
        if ResourceModel is None:
            return []
        from apps.resources.models import Resource

        return Resource.objects.filter(status="approved").order_by(
            "-download_count", "-view_count"
        )[:limit]

    def resolve_recent_resources(self, info, limit=10):
        """Get recent resources."""
        if ResourceModel is None:
            return []
        from apps.resources.models import Resource

        return Resource.objects.filter(status="approved").order_by("-created_at")[
            :limit
        ]

    def resolve_search(self, info, query, limit=20):
        """Search resources."""
        from apps.search.services import SearchService

        results = SearchService.search_resources(
            query=query,
            filters={},
            user=info.context.user if info.context.user.is_authenticated else None,
        )
        return results[:limit]


# ============== Input Types ==============
class UserInput(graphene.InputObjectType):
    """Input type for user registration."""

    username = graphene.String(required=True)
    email = graphene.String(required=True)
    password = graphene.String(required=True)
    first_name = graphene.String()
    last_name = graphene.String()
    course_id = graphene.Int()
    year_of_study = graphene.Int()


class ResourceInput(graphene.InputObjectType):
    """Input type for creating resources."""

    title = graphene.String(required=True)
    description = graphene.String()
    file = graphene.String(required=True)
    course_id = graphene.Int()
    unit_id = graphene.Int()
    tags = graphene.List(graphene.String)


# ============== Mutation Definitions ==============
class CreateUser(graphene.Mutation):
    """Mutation for creating a new user."""

    class Arguments:
        input = UserInput(required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, input):
        """Create a new user."""
        from apps.accounts.services import UserCreationService

        user_data = {
            "username": input.username,
            "email": input.email,
            "password": input.password,
            "first_name": input.get("first_name", ""),
            "last_name": input.get("last_name", ""),
        }

        user, success, message = UserCreationService.create_user(user_data)

        return cls(user=user if success else None, success=success, message=message)


class Mutation(graphene.ObjectType):
    """GraphQL mutations."""

    create_user = CreateUser.Field()


# ============== Schema ==============
schema = graphene.Schema(query=Query, mutation=Mutation)
