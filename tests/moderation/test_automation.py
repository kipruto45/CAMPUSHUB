"""Tests for moderation automation workflows."""
import pytest
from django.urls import reverse

from apps.courses.models import Course
from apps.faculties.models import Faculty, Department
from apps.comments.models import Comment
from apps.moderation.models import ModerationLog
from apps.notifications.models import Notification
from apps.reports.models import Report
from apps.resources.models import Resource


@pytest.fixture
def moderation_course(db):
    faculty = Faculty.objects.create(name='Applied Sciences', code='AS')
    department = Department.objects.create(faculty=faculty, name='Computing', code='COMP')
    return Course.objects.create(
        department=department,
        name='BSc Computing',
        code='BSC-COMP',
        duration_years=4,
    )


@pytest.mark.django_db
class TestModerationAutomation:
    """Automated moderation behavior across reports/resources."""

    def test_severe_report_auto_moves_resource_to_pending_and_in_review(
        self, authenticated_client, user, admin_user, moderator_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Automata Notes',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )

        response = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'resource': str(resource.id),
                'reason_type': 'copyright',
                'message': 'Possible copyright issue',
            },
            format='json',
        )
        assert response.status_code == 201

        resource.refresh_from_db()
        report = Report.objects.get(id=response.data['id'])

        assert resource.status == 'pending'
        assert report.status == 'in_review'
        assert ModerationLog.objects.filter(resource=resource, action='flagged').exists()
        assert Notification.objects.filter(
            recipient=admin_user,
            title='New Content Report',
        ).exists()
        assert Notification.objects.filter(
            recipient=moderator_user,
            title='New Content Report',
        ).exists()

    def test_report_threshold_auto_flags_resource(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        other_user_1 = type(user).objects.create_user(
            email='other1@test.com',
            password='pass12345',
            full_name='Other One',
            role='student',
        )
        other_user_2 = type(user).objects.create_user(
            email='other2@test.com',
            password='pass12345',
            full_name='Other Two',
            role='student',
        )

        resource = Resource.objects.create(
            title='Networks Notes',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )

        Report.objects.create(
            reporter=other_user_1,
            resource=resource,
            reason_type='other',
            message='Suspicious metadata',
        )
        Report.objects.create(
            reporter=other_user_2,
            resource=resource,
            reason_type='other',
            message='Wrong content',
        )

        response = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'resource': str(resource.id),
                'reason_type': 'other',
                'message': 'Does not match title',
            },
            format='json',
        )
        assert response.status_code == 201

        resource.refresh_from_db()
        report = Report.objects.get(id=response.data['id'])
        assert resource.status == 'pending'
        assert report.status == 'in_review'
        assert ModerationLog.objects.filter(resource=resource, action='flagged').exists()

    def test_resolve_report_notifies_reporter(
        self, moderator_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Compiler Notes',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        report = Report.objects.create(
            reporter=user,
            resource=resource,
            reason_type='inappropriate',
            message='Looks inappropriate',
        )

        response = moderator_client.post(
            f"{reverse('reports:report-detail', kwargs={'id': report.id})}resolve/",
            {'resolution_note': 'Reviewed and resolved'},
            format='json',
        )
        assert response.status_code == 200

        report.refresh_from_db()
        assert report.status == 'resolved'
        assert Notification.objects.filter(
            recipient=user,
            notification_type='report_update',
        ).exists()

    def test_severe_comment_report_auto_hides_and_locks_comment(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='OS Notes',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Potentially abusive statement',
        )

        response = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'comment': str(comment.id),
                'reason_type': 'abusive',
                'message': 'Abusive language',
            },
            format='json',
        )
        assert response.status_code == 201

        comment.refresh_from_db()
        report = Report.objects.get(id=response.data['id'])
        assert comment.is_locked is True
        assert comment.is_deleted is True
        assert report.status == 'in_review'
        assert Notification.objects.filter(
            recipient=admin_user,
            title='Comment Under Review',
        ).exists()
        assert ModerationLog.objects.filter(comment=comment, action='locked').exists()
        assert ModerationLog.objects.filter(comment=comment, action='hidden').exists()

    def test_locked_comment_cannot_be_updated_by_owner(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Algorithms Discussion',
            resource_type='notes',
            uploaded_by=user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=user,
            resource=resource,
            content='Initial content',
            is_locked=True,
        )

        response = authenticated_client.patch(
            reverse('comments:comment-detail', kwargs={'pk': comment.id}),
            {'content': 'Edited'},
            format='json',
        )
        assert response.status_code == 403

    def test_cannot_reply_to_locked_comment(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Databases Discussion',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        parent = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Locked parent',
            is_locked=True,
        )
        response = authenticated_client.post(
            reverse('comments:comment-list'),
            {
                'resource': str(resource.id),
                'parent': str(parent.id),
                'content': 'Reply attempt',
            },
            format='json',
        )
        assert response.status_code == 400

    def test_comment_report_threshold_auto_locks_comment(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        other_user_1 = type(user).objects.create_user(
            email='comment-other1@test.com',
            password='pass12345',
            full_name='Comment Other One',
            role='student',
        )
        other_user_2 = type(user).objects.create_user(
            email='comment-other2@test.com',
            password='pass12345',
            full_name='Comment Other Two',
            role='student',
        )
        resource = Resource.objects.create(
            title='AI Discussion',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Potential misinformation',
        )
        Report.objects.create(
            reporter=other_user_1,
            comment=comment,
            reason_type='other',
            message='Needs review',
        )
        Report.objects.create(
            reporter=other_user_2,
            comment=comment,
            reason_type='other',
            message='Suspicious',
        )
        response = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'comment': str(comment.id),
                'reason_type': 'other',
                'message': 'Third report threshold',
            },
            format='json',
        )
        assert response.status_code == 201

        comment.refresh_from_db()
        report = Report.objects.get(id=response.data['id'])
        assert comment.is_locked is True
        assert comment.is_deleted is True
        assert report.status == 'in_review'

    def test_comment_restored_when_last_active_report_dismissed(
        self, authenticated_client, moderator_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Security Discussion',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Original comment text',
        )

        report_create = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'comment': str(comment.id),
                'reason_type': 'abusive',
                'message': 'Abusive content',
            },
            format='json',
        )
        assert report_create.status_code == 201

        comment.refresh_from_db()
        assert comment.is_locked is True
        assert comment.moderation_hidden is True
        assert comment.content == '[hidden by moderation]'

        report_id = report_create.data['id']
        dismiss_response = moderator_client.post(
            f"{reverse('reports:report-detail', kwargs={'id': report_id})}dismiss/",
            {'resolution_note': 'Dismissed after review'},
            format='json',
        )
        assert dismiss_response.status_code == 200

        comment.refresh_from_db()
        assert comment.is_locked is False
        assert comment.is_deleted is False
        assert comment.moderation_hidden is False
        assert comment.content == 'Original comment text'
        assert ModerationLog.objects.filter(comment=comment, action='unlocked').exists()
        assert ModerationLog.objects.filter(comment=comment, action='restored').exists()

    def test_comment_not_restored_if_other_active_reports_exist(
        self, authenticated_client, moderator_client, user, admin_user, moderation_course
    ):
        second_reporter = type(user).objects.create_user(
            email='persist-active-report@test.com',
            password='pass12345',
            full_name='Persist Active Report',
            role='student',
        )
        resource = Resource.objects.create(
            title='ML Discussion',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Comment to moderate',
        )

        first_report = authenticated_client.post(
            reverse('reports:report-list'),
            {
                'comment': str(comment.id),
                'reason_type': 'abusive',
                'message': 'First severe report',
            },
            format='json',
        )
        assert first_report.status_code == 201

        second_report = Report.objects.create(
            reporter=second_reporter,
            comment=comment,
            reason_type='other',
            message='Second report still open',
            status='open',
        )

        dismiss_response = moderator_client.post(
            f"{reverse('reports:report-detail', kwargs={'id': first_report.data['id']})}dismiss/",
            {'resolution_note': 'Dismissed one report'},
            format='json',
        )
        assert dismiss_response.status_code == 200

        comment.refresh_from_db()
        second_report.refresh_from_db()
        assert second_report.status == 'open'
        assert comment.is_locked is True
        assert comment.moderation_hidden is True

    def test_moderator_can_lock_and_unlock_comment_manually(
        self, moderator_client, moderator_user, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Manual Moderation Thread',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=user,
            resource=resource,
            content='Needs manual moderation',
        )

        lock_response = moderator_client.post(
            reverse('comments:comment-lock', kwargs={'pk': comment.id}),
            {
                'reason': 'Manual lock for review',
                'hide_content': True,
            },
            format='json',
        )
        assert lock_response.status_code == 200

        comment.refresh_from_db()
        assert comment.is_locked is True
        assert comment.moderation_hidden is True
        assert comment.content == '[hidden by moderation]'
        assert ModerationLog.objects.filter(
            comment=comment,
            action='locked',
            reviewed_by=moderator_user,
        ).exists()
        assert ModerationLog.objects.filter(
            comment=comment,
            action='hidden',
            reviewed_by=moderator_user,
        ).exists()

        unlock_response = moderator_client.post(
            reverse('comments:comment-unlock', kwargs={'pk': comment.id}),
            {
                'reason': 'Manual unlock after review',
                'restore_content': True,
            },
            format='json',
        )
        assert unlock_response.status_code == 200

        comment.refresh_from_db()
        assert comment.is_locked is False
        assert comment.moderation_hidden is False
        assert comment.content == 'Needs manual moderation'
        assert ModerationLog.objects.filter(
            comment=comment,
            action='locked',
            reviewed_by=moderator_user,
        ).exists()
        assert ModerationLog.objects.filter(
            comment=comment,
            action='unlocked',
            reviewed_by=moderator_user,
        ).exists()
        assert ModerationLog.objects.filter(
            comment=comment,
            action='restored',
            reviewed_by=moderator_user,
        ).exists()

    def test_student_cannot_lock_comment_manually(
        self, authenticated_client, user, admin_user, moderation_course
    ):
        resource = Resource.objects.create(
            title='Permission Check Thread',
            resource_type='notes',
            uploaded_by=admin_user,
            course=moderation_course,
            status='approved',
            is_public=True,
        )
        comment = Comment.objects.create(
            user=admin_user,
            resource=resource,
            content='Visible comment',
        )
        response = authenticated_client.post(
            reverse('comments:comment-lock', kwargs={'pk': comment.id}),
            {
                'reason': 'Should fail',
                'hide_content': True,
            },
            format='json',
        )
        assert response.status_code == 403
