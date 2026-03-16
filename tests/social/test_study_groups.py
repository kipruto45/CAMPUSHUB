import pytest
from django.urls import reverse

from apps.resources.models import Resource
from apps.social.models import StudyGroup, StudyGroupMember, StudyGroupPost, StudyGroupResource


@pytest.fixture
def study_group_owner(db):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_user(
        email="group-owner@test.com",
        password="pass12345",
        full_name="Group Owner",
        registration_number="SG-OWNER-001",
        role="STUDENT",
    )


@pytest.fixture
def outsider(db):
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    return user_model.objects.create_user(
        email="outsider@test.com",
        password="pass12345",
        full_name="Out Sider",
        registration_number="SG-OUT-001",
        role="STUDENT",
    )


@pytest.mark.django_db
class TestStudyGroupsApi:
    def test_list_only_returns_public_or_membership_groups(
        self, authenticated_client, user, study_group_owner, outsider, course
    ):
        public_group = StudyGroup.objects.create(
            name="Public Group",
            description="Visible to everyone",
            creator=study_group_owner,
            course=course,
            is_public=True,
        )
        private_group = StudyGroup.objects.create(
            name="Private Group",
            description="Hidden group",
            creator=study_group_owner,
            course=course,
            is_public=False,
        )
        my_private_group = StudyGroup.objects.create(
            name="My Private Group",
            description="I belong here",
            creator=outsider,
            course=course,
            is_public=False,
        )
        StudyGroupMember.objects.create(group=my_private_group, user=user, role="member")

        response = authenticated_client.get(reverse("social:study-group-list"))

        assert response.status_code == 200
        names = {item["name"] for item in response.data["results"]}
        assert public_group.name in names
        assert my_private_group.name in names
        assert private_group.name not in names

    def test_create_group_adds_creator_membership(self, authenticated_client, user, course):
        response = authenticated_client.post(
            reverse("social:study-group-list"),
            {
                "name": "Algorithms Circle",
                "description": "Discuss algorithms weekly",
                "course_id": str(course.id),
                "is_public": False,
                "max_members": 12,
            },
            format="json",
        )

        assert response.status_code == 201
        group = StudyGroup.objects.get(id=response.data["id"])
        assert group.creator_id == user.id
        membership = StudyGroupMember.objects.get(group=group, user=user)
        assert membership.role == "admin"
        assert membership.status == "active"

    def test_join_and_leave_group(self, authenticated_client, user, study_group_owner, course):
        group = StudyGroup.objects.create(
            name="Data Structures",
            description="Practice group",
            creator=study_group_owner,
            course=course,
            is_public=True,
        )

        join_response = authenticated_client.post(
            reverse("social:study-group-join", kwargs={"group_id": group.id}),
            format="json",
        )
        assert join_response.status_code == 200
        assert StudyGroupMember.objects.filter(group=group, user=user, status="active").exists()

        leave_response = authenticated_client.post(
            reverse("social:study-group-leave", kwargs={"group_id": group.id}),
            format="json",
        )
        assert leave_response.status_code == 200
        assert not StudyGroupMember.objects.filter(group=group, user=user).exists()

    def test_members_posts_and_resources_endpoints(
        self, authenticated_client, user, study_group_owner, course
    ):
        group = StudyGroup.objects.create(
            name="Operating Systems",
            description="Kernel and processes",
            creator=study_group_owner,
            course=course,
            is_public=True,
        )
        StudyGroupMember.objects.create(group=group, user=user, role="member")
        StudyGroupMember.objects.create(group=group, user=study_group_owner, role="admin")

        post = StudyGroupPost.objects.create(
            group=group,
            author=study_group_owner,
            title="Week 1",
            content="Let's start with processes.",
        )
        resource = Resource.objects.create(
            title="OS Notes",
            resource_type="notes",
            uploaded_by=study_group_owner,
            course=course,
            status="approved",
            is_public=True,
        )
        StudyGroupResource.objects.create(
            group=group,
            resource=resource,
            shared_by=study_group_owner,
        )

        members_response = authenticated_client.get(
            reverse("social:study-group-members", kwargs={"group_id": group.id})
        )
        posts_response = authenticated_client.get(
            reverse("social:study-group-posts", kwargs={"group_id": group.id})
        )
        resources_response = authenticated_client.get(
            reverse("social:study-group-resources", kwargs={"group_id": group.id})
        )

        assert members_response.status_code == 200
        assert members_response.data["count"] == 2
        assert posts_response.status_code == 200
        assert posts_response.data["results"][0]["title"] == post.title
        assert resources_response.status_code == 200
        assert resources_response.data["results"][0]["title"] == resource.title

    def test_create_post_requires_membership(
        self, authenticated_client, study_group_owner, course
    ):
        group = StudyGroup.objects.create(
            name="Networks",
            description="Packet analysis",
            creator=study_group_owner,
            course=course,
            is_public=True,
        )

        response = authenticated_client.post(
            reverse("social:study-group-posts", kwargs={"group_id": group.id}),
            {"title": "Hello", "content": "I should not post yet."},
            format="json",
        )

        assert response.status_code == 403

    def test_private_group_detail_is_hidden_from_outsider(
        self, authenticated_client, study_group_owner, course
    ):
        group = StudyGroup.objects.create(
            name="Compiler Lab",
            description="Private compiler discussions",
            creator=study_group_owner,
            course=course,
            is_public=False,
        )

        response = authenticated_client.get(
            reverse("social:study-group-detail", kwargs={"group_id": group.id})
        )

        assert response.status_code == 403
