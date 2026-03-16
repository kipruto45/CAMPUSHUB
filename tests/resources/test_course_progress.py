import pytest
from django.urls import reverse

from apps.resources.models import CourseProgress, Resource


@pytest.mark.django_db
class TestCourseProgressRoutes:
    def test_get_course_progress_summary(self, authenticated_client, user, course):
        user.course = course
        user.save(update_fields=["course", "updated_at"])
        resource = Resource.objects.create(
            title="Linked Lists",
            resource_type="notes",
            uploaded_by=user,
            course=course,
            status="approved",
            is_public=True,
        )
        CourseProgress.objects.create(
            user=user,
            course=course,
            resource=resource,
            status="completed",
            completion_percentage=100,
            time_spent_minutes=25,
        )

        response = authenticated_client.get(
            reverse("courses:course-progress-detail", kwargs={"course_id": course.id})
        )

        assert response.status_code == 200
        assert response.data["course_id"] == str(course.id)
        assert response.data["total_resources"] == 1
        assert response.data["completed_resources"] == 1
        assert response.data["overall_percentage"] == 100.0

    def test_post_course_progress_update(self, authenticated_client, user, course):
        resource = Resource.objects.create(
            title="Queues",
            resource_type="notes",
            uploaded_by=user,
            course=course,
            status="approved",
            is_public=True,
        )

        response = authenticated_client.post(
            reverse("courses:course-progress-detail", kwargs={"course_id": course.id}),
            {
                "resource_id": str(resource.id),
                "status": "completed",
                "time_spent_minutes": 15,
            },
            format="json",
        )

        assert response.status_code == 200
        progress = CourseProgress.objects.get(user=user, course=course, resource=resource)
        assert progress.status == "completed"
        assert progress.time_spent_minutes == 15

    def test_list_all_course_progress_summaries(self, authenticated_client, user, course):
        user.course = course
        user.save(update_fields=["course", "updated_at"])
        resource = Resource.objects.create(
            title="Graphs",
            resource_type="notes",
            uploaded_by=user,
            course=course,
            status="approved",
            is_public=True,
        )
        CourseProgress.objects.create(
            user=user,
            course=course,
            resource=resource,
            status="in_progress",
            completion_percentage=50,
            time_spent_minutes=10,
        )

        response = authenticated_client.get(reverse("courses:course-progress-list"))

        assert response.status_code == 200
        assert response.data[0]["course_id"] == str(course.id)
        assert response.data[0]["in_progress_resources"] == 1
