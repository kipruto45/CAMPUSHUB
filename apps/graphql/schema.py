"""
GraphQL schema for CampusHub.
Expanded with comprehensive types, queries, and mutations.
"""

import graphene
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from graphene_django import DjangoListField, DjangoObjectType
from apps.payments.services import get_stripe_service
try:
    from apps.payments.providers import payment_service
except Exception:
    payment_service = None

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

try:
    from apps.announcements.models import Announcement as AnnouncementModel
except Exception:
    AnnouncementModel = None

try:
    from apps.notifications.models import Notification as NotificationModel
except Exception:
    NotificationModel = None

try:
    from apps.payments.models import (
        Plan as PlanModel,
        Subscription as SubscriptionModel,
        Payment as PaymentModel,
        StorageUpgrade as StorageUpgradeModel,
    )
except Exception:
    PlanModel = SubscriptionModel = PaymentModel = StorageUpgradeModel = None

try:
    from apps.calendar.models import AcademicCalendar as AcademicCalendarModel
    from apps.calendar.models import Timetable as TimetableModel
    from apps.calendar.models import TimetableOverride as TimetableOverrideModel
except Exception:
    AcademicCalendarModel = TimetableModel = TimetableOverrideModel = None

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


class UserProfileType(graphene.ObjectType):
    """Extended user profile with stats."""
    user = graphene.Field(UserType)
    resources_count = graphene.Int()
    downloads_count = graphene.Int()
    bookmarks_count = graphene.Int()
    following_count = graphene.Int()
    followers_count = graphene.Int()


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


# ============== Announcement Types ==============
if AnnouncementModel is not None:

    class AnnouncementType(DjangoObjectType):
        """GraphQL type for Announcement model."""

        class Meta:
            model = AnnouncementModel
            fields = (
                "id",
                "title",
                "content",
                "announcement_type",
                "priority",
                "is_pinned",
                "target_audience",
                "faculties",
                "departments",
                "courses",
                "year_of_study",
                "created_by",
                "created_at",
                "published_at",
                "expires_at",
                "view_count",
            )

else:

    class AnnouncementType(graphene.ObjectType):
        """Fallback Announcement type."""
        id = graphene.ID()
        title = graphene.String()


# ============== Notification Types ==============
if NotificationModel is not None:

    class NotificationType(DjangoObjectType):
        """GraphQL type for Notification model."""

        class Meta:
            model = NotificationModel
            fields = (
                "id",
                "title",
                "message",
                "notification_type",
                "priority",
                "is_read",
                "read_at",
                "recipient",
                "link",
                "created_at",
            )

else:

    class NotificationType(graphene.ObjectType):
        """Fallback Notification type."""
        id = graphene.ID()
        title = graphene.String()


# ============== Study Group Types ==============
class StudyGroupType(graphene.ObjectType):
    """GraphQL type for study groups."""
    id = graphene.ID()
    name = graphene.String()
    description = graphene.String()
    course = graphene.String()
    privacy = graphene.String()
    member_count = graphene.Int()
    creator = graphene.Field(UserType)
    created_at = graphene.String()


class StudyGroupMemberType(graphene.ObjectType):
    """GraphQL type for study group members."""
    user = graphene.Field(UserType)
    role = graphene.String()
    status = graphene.String()
    joined_at = graphene.String()


# ============== Message Types ==============
class MessageType(graphene.ObjectType):
    """GraphQL type for direct messages."""
    id = graphene.ID()
    sender = graphene.Field(UserType)
    recipient = graphene.Field(UserType)
    body = graphene.String()
    is_read = graphene.Boolean()
    read_at = graphene.String()
    created_at = graphene.String()


class ConversationType(graphene.ObjectType):
    """GraphQL type for conversations."""
    id = graphene.ID()
    name = graphene.String()
    is_group = graphene.Boolean()
    members = graphene.List(UserType)
    last_message = graphene.Field(MessageType)
    unread_count = graphene.Int()
    created_at = graphene.String()


# ============== Subscription/Plan Types ==============
class PlanType(graphene.ObjectType):
    """GraphQL type for subscription plans."""
    id = graphene.ID()
    name = graphene.String()
    tier = graphene.String()
    description = graphene.String()
    price_monthly = graphene.String()
    price_yearly = graphene.String()
    storage_limit_gb = graphene.Int()
    max_upload_size_mb = graphene.Int()
    download_limit_monthly = graphene.Int()
    can_download_unlimited = graphene.Boolean()
    has_ads = graphene.Boolean()


class SubscriptionType(graphene.ObjectType):
    """GraphQL type for user subscription."""
    id = graphene.ID()
    plan = graphene.Field(PlanType)
    status = graphene.String()
    current_period_start = graphene.String()
    current_period_end = graphene.String()


# ============== Calendar/Timetable Types ==============
class TimetableType(graphene.ObjectType):
    """GraphQL type for timetable entries."""
    id = graphene.ID()
    day = graphene.String()
    unit_code = graphene.String()
    unit_name = graphene.String()
    type = graphene.String()
    start_time = graphene.String()
    end_time = graphene.String()
    building = graphene.String()
    room = graphene.String()
    is_virtual = graphene.Boolean()


class PersonalScheduleType(graphene.ObjectType):
    """GraphQL type for personal schedules."""
    id = graphene.ID()
    title = graphene.String()
    description = graphene.String()
    category = graphene.String()
    date = graphene.String()
    start_time = graphene.String()
    end_time = graphene.String()
    is_all_day = graphene.Boolean()


class TodayScheduleType(graphene.ObjectType):
    """GraphQL type for today's schedule."""
    date = graphene.String()
    day = graphene.String()
    timetable = graphene.List(TimetableType)
    personal_events = graphene.List(PersonalScheduleType)


class DayScheduleType(graphene.ObjectType):
    """GraphQL type for a day's schedule."""
    date = graphene.String()
    timetable = graphene.List(TimetableType)
    personal_events = graphene.List(PersonalScheduleType)


class WeekScheduleType(graphene.ObjectType):
    """GraphQL type for week's schedule."""
    monday = graphene.Field(DayScheduleType)
    tuesday = graphene.Field(DayScheduleType)
    wednesday = graphene.Field(DayScheduleType)
    thursday = graphene.Field(DayScheduleType)
    friday = graphene.Field(DayScheduleType)
    saturday = graphene.Field(DayScheduleType)
    sunday = graphene.Field(DayScheduleType)
    cancel_at_period_end = graphene.Boolean()


class PaymentType(graphene.ObjectType):
    """GraphQL type for payments."""
    id = graphene.ID()
    amount = graphene.String()
    currency = graphene.String()
    status = graphene.String()
    payment_type = graphene.String()
    created_at = graphene.String()
    receipt_url = graphene.String()


class StorageUpgradeType(graphene.ObjectType):
    """GraphQL type for storage upgrades."""
    id = graphene.ID()
    storage_gb = graphene.Int()
    duration_days = graphene.Int()
    price = graphene.String()
    status = graphene.String()
    starts_at = graphene.String()
    ends_at = graphene.String()


# ============== Calendar Types ==============
class AcademicCalendarType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    faculty = graphene.Int()
    department = graphene.Int()
    year = graphene.String()
    semester = graphene.String()
    start_date = graphene.String()
    end_date = graphene.String()
    mid_semester_start = graphene.String()
    mid_semester_end = graphene.String()
    exam_start_date = graphene.String()
    exam_end_date = graphene.String()
    break_start_date = graphene.String()
    break_end_date = graphene.String()
    is_active = graphene.Boolean()


class TimetableType(graphene.ObjectType):
    id = graphene.ID()
    academic_calendar = graphene.ID()
    course = graphene.ID()
    unit = graphene.ID()
    day = graphene.String()
    start_time = graphene.String()
    end_time = graphene.String()
    type = graphene.String()
    building = graphene.String()
    room = graphene.String()
    is_virtual = graphene.Boolean()
    virtual_link = graphene.String()
    instructor = graphene.ID()
    instructor_name = graphene.String()
    year_of_study = graphene.Int()
    is_recurring = graphene.Boolean()
    weeks = graphene.List(graphene.Int)
    group_name = graphene.String()


class TimetableOverrideType(graphene.ObjectType):
    id = graphene.ID()
    timetable = graphene.ID()
    date = graphene.String()
    override_type = graphene.String()
    new_start_time = graphene.String()
    new_end_time = graphene.String()
    new_building = graphene.String()
    new_room = graphene.String()
    new_virtual_link = graphene.String()
    reason = graphene.String()


# ============== Query Definitions ==============
class Query(graphene.ObjectType):
    """GraphQL queries."""

    # User queries
    me = graphene.Field(UserType)
    user = graphene.Field(UserType, id=graphene.Int(), username=graphene.String())
    users = graphene.List(UserType, limit=graphene.Int())
    user_profile = graphene.Field(UserProfileType, username=graphene.String())

    # Resource queries
    resource = graphene.Field(ResourceType, id=graphene.Int())
    resources = (
        DjangoListField(ResourceType)
        if ResourceModel is not None
        else graphene.List(ResourceType)
    )
    popular_resources = graphene.List(ResourceType, limit=graphene.Int())
    recent_resources = graphene.List(ResourceType, limit=graphene.Int())
    my_uploads = graphene.List(ResourceType, limit=graphene.Int())

    # Course queries
    courses = graphene.List(CourseType, limit=graphene.Int())
    course = graphene.Field(CourseType, id=graphene.Int(), code=graphene.String())

    # Unit queries
    units = graphene.List(UnitType, course_id=graphene.Int(), limit=graphene.Int())
    unit = graphene.Field(UnitType, id=graphene.Int(), code=graphene.String())

    # Announcement queries
    announcements = graphene.List(AnnouncementType, limit=graphene.Int())
    announcement = graphene.Field(AnnouncementType, id=graphene.Int())

    # Notification queries
    notifications = graphene.List(NotificationType, limit=graphene.Int(), unread_only=graphene.Boolean())
    unread_notification_count = graphene.Int()

    # Study group queries
    study_groups = graphene.List(StudyGroupType, limit=graphene.Int())
    my_study_groups = graphene.List(StudyGroupType)
    study_group = graphene.Field(StudyGroupType, id=graphene.ID())

    # Message queries
    conversations = graphene.List(ConversationType)
    messages = graphene.List(MessageType, conversation_id=graphene.ID(), limit=graphene.Int())

    # Payment queries
    current_subscription = graphene.Field(SubscriptionType)
    available_plans = graphene.List(PlanType)

    # Calendar queries
    my_timetable = graphene.List(TimetableType)
    today_schedule = graphene.Field(TodayScheduleType)
    week_schedule = graphene.Field(WeekScheduleType)
    personal_schedules = graphene.List(PersonalScheduleType)
    payment_history = graphene.List(PaymentType, limit=graphene.Int())
    storage_upgrades = graphene.List(StorageUpgradeType, limit=graphene.Int())
    calendars = graphene.List(
        AcademicCalendarType,
        faculty_id=graphene.Int(),
        department_id=graphene.Int(),
        year=graphene.String(),
        semester=graphene.String(),
        is_active=graphene.Boolean(),
    )
    timetables = graphene.List(
        TimetableType,
        calendar_id=graphene.ID(),
        course_id=graphene.ID(),
        unit_id=graphene.ID(),
        day=graphene.String(),
        year_of_study=graphene.Int(),
        limit=graphene.Int(),
    )
    timetable = graphene.Field(TimetableType, id=graphene.ID(required=True))
    timetable_overrides = graphene.List(
        TimetableOverrideType, timetable_id=graphene.ID(required=True)
    )

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

    def resolve_user_profile(self, info, username):
        """Get extended user profile."""
        try:
            user = User.objects.get(username=username)
            return UserProfileType(
                user=user,
                resources_count=user.uploaded_resources.filter(status="approved").count(),
                downloads_count=user.downloads.count(),
                bookmarks_count=user.bookmarks.count(),
                following_count=user.following.count(),
                followers_count=user.followers.count(),
            )
        except User.DoesNotExist:
            return None

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

    def resolve_my_uploads(self, info, limit=10):
        """Get current user's uploaded resources."""
        if not info.context.user.is_authenticated:
            return []
        if ResourceModel is None:
            return []
        from apps.resources.models import Resource

        return Resource.objects.filter(
            uploaded_by=info.context.user
        ).order_by("-created_at")[:limit]

    def resolve_courses(self, info, limit=20):
        """Get all courses."""
        if CourseModel is None:
            return []
        from apps.courses.models import Course

        return Course.objects.all()[:limit]

    def resolve_course(self, info, id=None, code=None):
        """Get course by ID or code."""
        if CourseModel is None:
            return None
        from apps.courses.models import Course

        if id:
            return Course.objects.get(pk=id)
        if code:
            return Course.objects.get(code=code)
        return None

    def resolve_units(self, info, course_id=None, limit=20):
        """Get units, optionally filtered by course."""
        if UnitModel is None:
            return []
        from apps.courses.models import Unit

        qs = Unit.objects.all()
        if course_id:
            qs = qs.filter(course_id=course_id)
        return qs[:limit]

    def resolve_unit(self, info, id=None, code=None):
        """Get unit by ID or code."""
        if UnitModel is None:
            return None
        from apps.courses.models import Unit

        if id:
            return Unit.objects.get(pk=id)
        if code:
            return Unit.objects.get(code=code)
        return None

    def resolve_announcements(self, info, limit=20):
        """Get announcements."""
        if AnnouncementModel is None:
            return []
        from apps.announcements.models import Announcement

        return Announcement.objects.filter(status="published").order_by("-is_pinned", "-published_at")[:limit]

    def resolve_announcement(self, info, id):
        """Get announcement by ID."""
        if AnnouncementModel is None:
            return None
        from apps.announcements.models import Announcement

        return Announcement.objects.get(pk=id)

    def resolve_notifications(self, info, limit=20, unread_only=False):
        """Get notifications for current user."""
        if not info.context.user.is_authenticated:
            return []
        if NotificationModel is None:
            return []
        from apps.notifications.models import Notification

        qs = Notification.objects.filter(recipient=info.context.user)
        if unread_only:
            qs = qs.filter(is_read=False)
        return qs.order_by("-created_at")[:limit]

    def resolve_unread_notification_count(self, info):
        """Get count of unread notifications."""
        if not info.context.user.is_authenticated:
            return 0
        if NotificationModel is None:
            return 0
        from apps.notifications.models import Notification

        return Notification.objects.filter(
            recipient=info.context.user,
            is_read=False
        ).count()

    def resolve_study_groups(self, info, limit=20):
        """Get public study groups."""
        from apps.social.models import StudyGroup

        return StudyGroup.objects.filter(
            status="active",
            privacy="public"
        ).order_by("-created_at")[:limit]

    def resolve_my_study_groups(self, info):
        """Get study groups user is member of."""
        if not info.context.user.is_authenticated:
            return []
        from apps.social.models import StudyGroupMember

        member_groups = StudyGroupMember.objects.filter(
            user=info.context.user,
            status="active"
        ).values_list("group_id", flat=True)

        from apps.social.models import StudyGroup
        return StudyGroup.objects.filter(id__in=member_groups, status="active")

    def resolve_study_group(self, info, id):
        """Get study group by ID."""
        from apps.social.models import StudyGroup

        return StudyGroup.objects.get(pk=id)

    def resolve_conversations(self, info):
        """Get user's conversations."""
        if not info.context.user.is_authenticated:
            return []
        from apps.social.models import Conversation

        return Conversation.objects.filter(
            members=info.context.user
        ).order_by("-created_at")

    def resolve_messages(self, info, conversation_id, limit=50):
        """Get messages in a conversation."""
        if not info.context.user.is_authenticated:
            return []
        from apps.social.models import ConversationMessage

        return ConversationMessage.objects.filter(
            conversation_id=conversation_id,
            conversation__members=info.context.user
        ).order_by("-created_at")[:limit]

    def resolve_current_subscription(self, info):
        """Get user's current subscription."""
        if not info.context.user.is_authenticated:
            return None
        if SubscriptionModel is None or PlanModel is None:
            return None

        sub = SubscriptionModel.objects.filter(
            user=info.context.user,
            status__in=["active", "trialing", "past_due"]
        ).select_related("plan").first()

        if sub:
            return SubscriptionType(
                id=str(sub.id),
                plan=PlanType(
                    id=str(sub.plan.id),
                    name=sub.plan.name,
                    tier=sub.plan.tier,
                    description=sub.plan.description,
                    price_monthly=str(sub.plan.price_monthly),
                    price_yearly=str(sub.plan.price_yearly),
                    storage_limit_gb=sub.plan.storage_limit_gb,
                    max_upload_size_mb=sub.plan.max_upload_size_mb,
                    download_limit_monthly=sub.plan.download_limit_monthly,
                    can_download_unlimited=sub.plan.can_download_unlimited,
                    has_ads=sub.plan.has_ads,
                ),
                status=sub.status,
                current_period_start=str(sub.current_period_start) if sub.current_period_start else None,
                current_period_end=str(sub.current_period_end) if sub.current_period_end else None,
                cancel_at_period_end=sub.cancel_at_period_end,
            )
        return None

    def resolve_available_plans(self, info):
        """Get all available subscription plans."""
        if PlanModel is None:
            return []
        return PlanModel.objects.filter(is_active=True).order_by("display_order")

    def resolve_payment_history(self, info, limit=20):
        """Get recent payments for the authenticated user."""
        if not info.context.user.is_authenticated:
            return []
        if PaymentModel is None:
            return []
        payments = PaymentModel.objects.filter(user=info.context.user).order_by("-created_at")[:limit]
        return [
            PaymentType(
                id=str(p.id),
                amount=str(p.amount),
                currency=p.currency,
                status=p.status,
                payment_type=p.payment_type,
                created_at=str(p.created_at),
                receipt_url=p.receipt_url,
            )
            for p in payments
        ]

    def resolve_storage_upgrades(self, info, limit=20):
        """Get storage upgrades for the authenticated user."""
        if not info.context.user.is_authenticated:
            return []
        if StorageUpgradeModel is None:
            return []
        upgrades = StorageUpgradeModel.objects.filter(user=info.context.user).order_by("-created_at")[:limit]
        return [
            StorageUpgradeType(
                id=str(u.id),
                storage_gb=u.storage_gb,
                duration_days=u.duration_days,
                price=str(u.price),
                status=u.status,
                starts_at=str(u.starts_at) if u.starts_at else None,
                ends_at=str(u.ends_at) if u.ends_at else None,
            )
            for u in upgrades
        ]

    def resolve_calendars(self, info, faculty_id=None, department_id=None, year=None, semester=None, is_active=True):
        if AcademicCalendarModel is None:
            return []
        qs = AcademicCalendarModel.objects.all()
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if faculty_id:
            qs = qs.filter(faculty_id=faculty_id)
        if department_id:
            qs = qs.filter(department_id=department_id)
        if year:
            qs = qs.filter(year=str(year))
        if semester:
            qs = qs.filter(semester=str(semester))
        return [
            AcademicCalendarType(
                id=str(c.id),
                name=c.name,
                faculty=c.faculty_id,
                department=c.department_id,
                year=c.year,
                semester=c.semester,
                start_date=str(c.start_date),
                end_date=str(c.end_date),
                mid_semester_start=str(c.mid_semester_start) if c.mid_semester_start else None,
                mid_semester_end=str(c.mid_semester_end) if c.mid_semester_end else None,
                exam_start_date=str(c.exam_start_date) if c.exam_start_date else None,
                exam_end_date=str(c.exam_end_date) if c.exam_end_date else None,
                break_start_date=str(c.break_start_date) if c.break_start_date else None,
                break_end_date=str(c.break_end_date) if c.break_end_date else None,
                is_active=c.is_active,
            )
            for c in qs
        ]

    def resolve_timetables(self, info, calendar_id=None, course_id=None, unit_id=None, day=None, year_of_study=None, limit=200):
        if TimetableModel is None:
            return []
        qs = TimetableModel.objects.select_related("course", "unit", "instructor", "academic_calendar")
        if calendar_id:
            qs = qs.filter(academic_calendar_id=calendar_id)
        if course_id:
            qs = qs.filter(course_id=course_id)
        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        if day:
            qs = qs.filter(day=day.lower())
        if year_of_study:
            qs = qs.filter(year_of_study=year_of_study)

        qs = qs.order_by("day", "start_time")[:limit]
        return [
            TimetableType(
                id=str(t.id),
                academic_calendar=str(t.academic_calendar_id),
                course=str(t.course_id),
                unit=str(t.unit_id) if t.unit_id else None,
                day=t.day,
                start_time=str(t.start_time),
                end_time=str(t.end_time),
                type=t.type,
                building=t.building,
                room=t.room,
                is_virtual=t.is_virtual,
                virtual_link=t.virtual_link,
                instructor=str(t.instructor_id) if t.instructor_id else None,
                instructor_name=(t.instructor.get_full_name() or t.instructor.email) if t.instructor else None,
                year_of_study=t.year_of_study,
                is_recurring=t.is_recurring,
                weeks=[int(w) for w in t.weeks] if t.weeks else [],
                group_name=t.group_name,
            )
            for t in qs
        ]

    def resolve_timetable(self, info, id):
        if TimetableModel is None:
            return None
        try:
            t = TimetableModel.objects.select_related("instructor", "course", "unit").get(pk=id)
        except TimetableModel.DoesNotExist:
            return None
        return TimetableType(
            id=str(t.id),
            academic_calendar=str(t.academic_calendar_id),
            course=str(t.course_id),
            unit=str(t.unit_id) if t.unit_id else None,
            day=t.day,
            start_time=str(t.start_time),
            end_time=str(t.end_time),
            type=t.type,
            building=t.building,
            room=t.room,
            is_virtual=t.is_virtual,
            virtual_link=t.virtual_link,
            instructor=str(t.instructor_id) if t.instructor_id else None,
            instructor_name=(t.instructor.get_full_name() or t.instructor.email) if t.instructor else None,
            year_of_study=t.year_of_study,
            is_recurring=t.is_recurring,
            weeks=[int(w) for w in t.weeks] if t.weeks else [],
            group_name=t.group_name,
        )

    def resolve_timetable_overrides(self, info, timetable_id):
        if TimetableOverrideModel is None:
            return []
        qs = TimetableOverrideModel.objects.filter(timetable_id=timetable_id).order_by("-date")
        return [
            TimetableOverrideType(
                id=str(o.id),
                timetable=str(o.timetable_id),
                date=str(o.date),
                override_type=o.override_type,
                new_start_time=str(o.new_start_time) if o.new_start_time else None,
                new_end_time=str(o.new_end_time) if o.new_end_time else None,
                new_building=o.new_building,
                new_room=o.new_room,
                new_virtual_link=o.new_virtual_link,
                reason=o.reason,
            )
            for o in qs
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


class MessageInput(graphene.InputObjectType):
    """Input type for sending messages."""

    recipient_id = graphene.Int(required=True)
    body = graphene.String(required=True)


class StudyGroupInput(graphene.InputObjectType):
    """Input type for creating study groups."""

    name = graphene.String(required=True)
    description = graphene.String()
    course_id = graphene.Int()
    privacy = graphene.String()
    max_members = graphene.Int()


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


class SendMessage(graphene.Mutation):
    """Mutation for sending a direct message."""

    class Arguments:
        input = MessageInput(required=True)

    message = graphene.Field(MessageType)
    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, input):
        """Send a message to another user."""
        if not info.context.user.is_authenticated:
            return cls(message=None, success=False)

        from apps.social.models import Message
        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            recipient = User.objects.get(pk=input.recipient_id)
            message = Message.objects.create(
                sender=info.context.user,
                recipient=recipient,
                body=input.body,
            )
            return cls(message=message, success=True)
        except User.DoesNotExist:
            return cls(message=None, success=False)


class CreateStudyGroup(graphene.Mutation):
    """Mutation for creating a study group."""

    class Arguments:
        input = StudyGroupInput(required=True)

    study_group = graphene.Field(StudyGroupType)
    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, input):
        """Create a new study group."""
        if not info.context.user.is_authenticated:
            return cls(study_group=None, success=False)

        from apps.social.models import StudyGroup

        course = None
        if input.get("course_id"):
            from apps.courses.models import Course
            try:
                course = Course.objects.get(pk=input.course_id)
            except Course.DoesNotExist:
                pass

        group = StudyGroup.objects.create(
            name=input.name,
            description=input.get("description", ""),
            course=course,
            privacy=input.get("privacy", "public"),
            max_members=input.get("max_members", 10),
            creator=info.context.user,
        )

        # Add creator as admin
        from apps.social.models import StudyGroupMember
        StudyGroupMember.objects.create(
            user=info.context.user,
            group=group,
            role="admin",
        )

        return cls(study_group=group, success=True)


class MarkNotificationRead(graphene.Mutation):
    """Mutation for marking notification as read."""

    class Arguments:
        notification_id = graphene.Int(required=True)

    success = graphene.Boolean()

    @classmethod
    def mutate(cls, root, info, notification_id):
        """Mark notification as read."""
        if not info.context.user.is_authenticated:
            return cls(success=False)

        from apps.notifications.models import Notification

        try:
            notification = Notification.objects.get(
                pk=notification_id,
                recipient=info.context.user
            )
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            return cls(success=True)
        except Notification.DoesNotExist:
            return cls(success=False)


class StartCheckout(graphene.Mutation):
    """Create a Stripe checkout session for a subscription."""

    class Arguments:
        plan_id = graphene.ID(required=True)
        billing_period = graphene.String(required=False, default_value="monthly")
        provider = graphene.String(required=False, default_value="stripe")

    checkout_url = graphene.String()
    session_id = graphene.String()
    instructions = graphene.JSONString()
    provider = graphene.String()
    provider_payment_id = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, plan_id, billing_period="monthly", provider="stripe"):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")
        if PlanModel is None:
            return cls(success=False, message="Payments not enabled")
        try:
            plan = PlanModel.objects.get(pk=plan_id, is_active=True)
        except PlanModel.DoesNotExist:
            return cls(success=False, message="Plan not found")

        # Stripe path (existing behaviour)
        if provider == "stripe":
            price_id = plan.stripe_monthly_price_id if billing_period == "monthly" else plan.stripe_yearly_price_id
            if not price_id:
                return cls(success=False, message="Plan not available for purchase")

            stripe = get_stripe_service()
            customer = stripe.get_or_create_customer(info.context.user)
            base_url = getattr(settings, "BASE_URL", "http://localhost:8000")

            session = stripe.create_checkout_session(
                customer_id=customer.id,
                price_id=price_id,
                success_url=f"{base_url}/settings/billing/success/",
                cancel_url=f"{base_url}/settings/billing/cancel/",
                metadata={
                    "user_id": str(info.context.user.id),
                    "plan_id": str(plan.id),
                    "billing_period": billing_period,
                },
            )
            return cls(
                provider="stripe",
                checkout_url=session.url,
                session_id=session.id,
                success=True,
                message="Checkout session created",
            )

        # Non-Stripe providers via payment service
        if payment_service is None:
            return cls(success=False, message="Payment service unavailable")

        amount = plan.price_monthly if billing_period == "monthly" else plan.price_yearly
        result = payment_service.create_payment(
            provider=provider,
            amount=amount,
            currency="USD",
            description=f"{plan.name} subscription",
            user=info.context.user,
            payment_type="subscription",
            plan_id=str(plan.id),
            billing_period=billing_period,
        )

        if not result.get("success"):
            return cls(success=False, message=result.get("error", "Payment creation failed"))

        return cls(
            provider=provider,
            checkout_url=result.get("checkout_url"),
            instructions=result.get("instructions"),
            provider_payment_id=result.get("payment_id"),
            success=True,
            message="Payment created",
        )


class BillingPortal(graphene.Mutation):
    """Open Stripe billing portal for the authenticated user."""

    portal_url = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")
        if SubscriptionModel is None:
            return cls(success=False, message="Payments not enabled")
        subscription = SubscriptionModel.objects.filter(
            user=info.context.user,
            stripe_customer_id__isnull=False,
        ).first()
        if not subscription or not subscription.stripe_customer_id:
            return cls(success=False, message="No billing account found")

        stripe = get_stripe_service()
        base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
        portal = stripe.create_portal_session(
            customer_id=subscription.stripe_customer_id,
            return_url=f"{base_url}/settings/billing/",
        )
        return cls(portal_url=portal.url, success=True, message="Portal created")


class StorageUpgrade(graphene.Mutation):
    """Purchase a storage upgrade via payment intent."""

    class Arguments:
        storage_gb = graphene.Int(required=True)
        duration_days = graphene.Int(required=False, default_value=30)
        provider = graphene.String(required=False, default_value="stripe")

    client_secret = graphene.String()
    upgrade_id = graphene.String()
    amount = graphene.String()
    checkout_url = graphene.String()
    instructions = graphene.JSONString()
    provider_payment_id = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, storage_gb, duration_days=30, provider="stripe"):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")
        if StorageUpgradeModel is None:
            return cls(success=False, message="Payments not enabled")

        if storage_gb not in [5, 10, 20, 50, 100]:
            return cls(success=False, message="Invalid storage amount")

        price_per_gb = Decimal("2.00")
        total_price = price_per_gb * Decimal(storage_gb) * Decimal(duration_days) / Decimal(30)

        # Stripe path
        if provider == "stripe":
            stripe = get_stripe_service()
            customer = stripe.get_or_create_customer(info.context.user)

            intent = stripe.create_payment_intent(
                amount=total_price,
                customer_id=customer.id,
                metadata={
                    "user_id": str(info.context.user.id),
                    "storage_gb": str(storage_gb),
                    "duration_days": str(duration_days),
                    "type": "storage_upgrade",
                },
            )

            upgrade = StorageUpgradeModel.objects.create(
                user=info.context.user,
                storage_gb=storage_gb,
                duration_days=duration_days,
                price=total_price,
                stripe_price_id=intent.id,
            )

            return cls(
                client_secret=intent.client_secret,
                upgrade_id=str(upgrade.id),
                amount=str(total_price),
                success=True,
                message="Upgrade intent created",
            )

        if payment_service is None:
            return cls(success=False, message="Payment service unavailable")

        upgrade = StorageUpgradeModel.objects.create(
            user=info.context.user,
            storage_gb=storage_gb,
            duration_days=duration_days,
            price=total_price,
            status="pending",
        )

        result = payment_service.create_payment(
            provider=provider,
            amount=total_price,
            currency="USD",
            description="Storage upgrade",
            user=info.context.user,
            payment_type="one_time",
            type="storage_upgrade",
            upgrade_id=str(upgrade.id),
            storage_gb=storage_gb,
            duration_days=duration_days,
        )

        if not result.get("success"):
            upgrade.status = "canceled"
            upgrade.save(update_fields=["status", "updated_at"])
            return cls(success=False, message=result.get("error", "Payment creation failed"))

        upgrade.payment_id = result.get("local_payment_id")
        upgrade.save(update_fields=["payment", "updated_at"])

        return cls(
            checkout_url=result.get("checkout_url"),
            instructions=result.get("instructions"),
            provider_payment_id=result.get("payment_id"),
            upgrade_id=str(upgrade.id),
            amount=str(total_price),
            success=True,
            message="Upgrade payment created",
        )


class ImportTimetable(graphene.Mutation):
    """Mutation for importing timetable from CSV/ICS."""

    class Arguments:
        file_content = graphene.String(required=True)
        import_type = graphene.String(required=True)  # csv, ics

    success = graphene.Boolean()
    message = graphene.String()
    imported_count = graphene.Int()

    @classmethod
    def mutate(cls, root, info, file_content, import_type):
        """Import timetable from file."""
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required", imported_count=0)

        from apps.calendar.services import TimetableImportService

        result = TimetableImportService.import_timetable(
            file_content=file_content,
            import_type=import_type,
            user=info.context.user
        )

        return cls(
            success=result['success'],
            message=result['message'],
            imported_count=result.get('imported_count', 0)
        )


class CreatePaymentIntent(graphene.Mutation):
    """Create a payment with any supported provider."""

    class Arguments:
        provider = graphene.String(required=True)  # stripe, paypal, mobile_money
        amount = graphene.Decimal(required=True)
        currency = graphene.String(required=False, default_value="USD")
        description = graphene.String(required=False)
        phone_number = graphene.String(required=False)  # For mobile money

    checkout_url = graphene.String()
    payment_id = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()
    provider = graphene.String()

    @classmethod
    def mutate(cls, root, info, provider, amount, currency="USD", description=None, phone_number=None):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")

        from apps.payments.providers import payment_service

        metadata = {}
        if description:
            metadata["description"] = description
        if phone_number:
            metadata["phone_number"] = phone_number

        result = payment_service.create_payment(
            provider=provider,
            amount=Decimal(str(amount)),
            currency=currency,
            description=description,
            user=info.context.user,
            success_url=getattr(settings, "BASE_URL", "http://localhost:8000") + "/settings/billing/success/",
            cancel_url=getattr(settings, "BASE_URL", "http://localhost:8000") + "/settings/billing/cancel/",
            **metadata
        )

        return cls(
            checkout_url=result.get("checkout_url"),
            payment_id=result.get("payment_id"),
            success=result.get("success", False),
            message=result.get("error", "Payment created"),
            provider=provider,
        )


class VerifyPayment(graphene.Mutation):
    """Verify payment status."""

    class Arguments:
        provider = graphene.String(required=True)
        payment_id = graphene.String(required=True)

    status = graphene.String()
    amount = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, provider, payment_id):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")

        from apps.payments.providers import payment_service

        result = payment_service.verify_payment(provider, payment_id)

        return cls(
            status=result.get("status"),
            amount=str(result.get("amount", "")),
            success=result.get("success", False),
            message=result.get("error", ""),
        )


class RefundPayment(graphene.Mutation):
    """Refund a payment."""

    class Arguments:
        payment_id = graphene.ID(required=True)
        amount = graphene.Decimal(required=False)  # Optional partial refund

    refund_id = graphene.String()
    success = graphene.Boolean()
    message = graphene.String()

    @classmethod
    def mutate(cls, root, info, payment_id, amount=None):
        if not info.context.user.is_authenticated:
            return cls(success=False, message="Authentication required")

        # Check permissions - only admin can refund
        if not info.context.user.is_staff:
            return cls(success=False, message="Admin permission required")

        from apps.payments.providers import payment_service
        from apps.payments.models import Payment

        try:
            payment = Payment.objects.get(pk=payment_id)
            provider = payment.metadata.get("provider", "stripe")
            
            result = payment_service.refund_payment(
                provider=provider,
                payment_id=str(payment.id),
                amount=Decimal(str(amount)) if amount else None
            )

            return cls(
                refund_id=result.get("refund_id"),
                success=result.get("success", False),
                message=result.get("error", "Refund processed"),
            )
        except Payment.DoesNotExist:
            return cls(success=False, message="Payment not found")


class Mutation(graphene.ObjectType):
    """GraphQL mutations."""

    create_user = CreateUser.Field()
    send_message = SendMessage.Field()
    create_study_group = CreateStudyGroup.Field()
    mark_notification_read = MarkNotificationRead.Field()
    start_checkout = StartCheckout.Field()
    billing_portal = BillingPortal.Field()
    storage_upgrade = StorageUpgrade.Field()
    import_timetable = ImportTimetable.Field()
    
    # Multi-provider payment mutations
    create_payment_intent = CreatePaymentIntent.Field()
    verify_payment = VerifyPayment.Field()
    refund_payment = RefundPayment.Field()


# ============== Schema ==============
schema = graphene.Schema(query=Query, mutation=Mutation)
