"""
Management command to seed all reference data for CampusHub.
Run with: python manage.py seed_all_data
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
import uuid

from apps.accounts.models import User
from apps.courses.models import Course, Unit
from apps.faculties.models import Faculty, Department
from apps.resources.models import Resource
from apps.announcements.models import Announcement
from apps.gamification.models import Badge, BadgeCategory, AchievementTier, AchievementCategory
from apps.social.models import StudyGroup


class Command(BaseCommand):
    help = 'Seed all reference data for CampusHub'

    def handle(self, *args, **options):
        self.stdout.write('Starting data seeding...')

        # Ensure admin exists
        admin, created = User.objects.get_or_create(
            email='admin@campushub.com',
            defaults={
                'first_name': 'System',
                'last_name': 'Admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin.set_password('admin123')
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Created admin user: {admin.email}'))
        else:
            self.stdout.write(f'Admin user already exists: {admin.email}')

        # Get sample course and unit for associations
        course = Course.objects.first()
        unit = Unit.objects.first()

        if not course or not unit:
            self.stdout.write(self.style.ERROR('No courses or units found. Run migrations and seed courses first.'))
            return

        # Create Resources
        self._seed_resources(admin, course, unit)

        # Create Announcements
        self._seed_announcements(admin)

        # Create Badges and Gamification
        self._seed_gamification()

        # Create Study Groups
        self._seed_study_groups(admin, course)

        self.stdout.write(self.style.SUCCESS('=== Data seeding completed! ==='))
        self._print_summary()

    def _seed_resources(self, admin, course, unit):
        resources = [
            {'title': 'Introduction to Accounting Notes', 'description': 'Comprehensive notes for accounting basics', 'resource_type': 'notes'},
            {'title': 'Calculus Past Papers 2023', 'description': 'Previous year exam papers', 'resource_type': 'past_paper'},
            {'title': 'Programming Assignment Solutions', 'description': 'Complete solutions to assignments', 'resource_type': 'assignment'},
            {'title': 'Business Law Textbook', 'description': 'Complete business law reference', 'resource_type': 'book'},
            {'title': 'Statistics Slides Week 1-5', 'description': 'Lecture slides for statistics', 'resource_type': 'slides'},
        ]

        for r in resources:
            slug = slugify(r['title']) + '-' + str(uuid.uuid4())[:8]
            Resource.objects.get_or_create(
                title=r['title'],
                defaults={
                    'description': r['description'],
                    'resource_type': r['resource_type'],
                    'uploaded_by': admin,
                    'course': course,
                    'unit': unit,
                    'slug': slug,
                    'status': 'approved',
                    'approved_by': admin,
                    'approved_at': timezone.now(),
                }
            )
        self.stdout.write(f'Created {len(resources)} Resources')

    def _seed_announcements(self, admin):
        announcements = [
            {'title': 'Welcome to CampusHub', 'content': 'Welcome to the new campus management system! Explore courses, units, and connect with fellow students.', 'announcement_type': 'urgent'},
            {'title': 'Exam Schedule Released', 'content': 'The final exam schedule has been published. Please check your dashboard for details.', 'announcement_type': 'academic'},
            {'title': 'Library Hours Extended', 'content': 'Library will be open 24/7 during the exam period to help with your studies.', 'announcement_type': 'general'},
            {'title': 'New Resources Available', 'content': 'New study materials have been uploaded by our faculty. Check the resources section.', 'announcement_type': 'course_update'},
        ]

        for a in announcements:
            slug = slugify(a['title']) + '-' + str(uuid.uuid4())[:8]
            Announcement.objects.get_or_create(
                title=a['title'],
                defaults={
                    'content': a['content'],
                    'announcement_type': a['announcement_type'],
                    'status': 'published',
                    'created_by': admin,
                    'slug': slug,
                    'published_at': timezone.now(),
                }
            )
        self.stdout.write(f'Created {len(announcements)} Announcements')

    def _seed_gamification(self):
        # Badge Categories
        bc1 = BadgeCategory.objects.get_or_create(name='Learning', defaults={'description': 'Academic achievements'})[0]
        bc2 = BadgeCategory.objects.get_or_create(name='Social', defaults={'description': 'Social interactions'})[0]
        bc3 = BadgeCategory.objects.get_or_create(name='Streak', defaults={'description': 'Daily engagement'})[0]

        badges = [
            {'name': 'First Login', 'description': 'Logged in for the first time', 'category': bc3, 'points_required': 10},
            {'name': 'Study Streak 7', 'description': '7 days of continuous learning', 'category': bc3, 'points_required': 100},
            {'name': 'Resource Contributor', 'description': 'Uploaded 5 resources', 'category': bc2, 'points_required': 50},
            {'name': 'Top Contributor', 'description': 'Most active contributor of the month', 'category': bc2, 'points_required': 200},
            {'name': 'Quiz Master', 'description': 'Completed 10 quizzes with 80%+ score', 'category': bc1, 'points_required': 150},
            {'name': 'Course Complete', 'description': 'Completed all units in a course', 'category': bc1, 'points_required': 300},
            {'name': 'Helping Hand', 'description': 'Helped 10 other students', 'category': bc2, 'points_required': 100},
            {'name': 'Night Owl', 'description': 'Studied between midnight and 4am', 'category': bc3, 'points_required': 25},
        ]

        for b in badges:
            slug = slugify(b['name'])
            Badge.objects.get_or_create(
                name=b['name'],
                defaults={
                    'description': b['description'],
                    'category': b['category'],
                    'points_required': b['points_required'],
                    'slug': slug,
                    'icon': 'award',
                }
            )

        # Achievement Categories
        AchievementCategory.objects.get_or_create(name='Learning', defaults={'description': 'Academic achievements'})
        AchievementCategory.objects.get_or_create(name='Social', defaults={'description': 'Social interactions'})
        AchievementCategory.objects.get_or_create(name='Engagement', defaults={'description': 'Platform engagement'})
        AchievementCategory.objects.get_or_create(name='Special', defaults={'description': 'Special events'})

        # Achievement Tiers
        tiers = [
            {'name': 'Bronze', 'multiplier': 1.0},
            {'name': 'Silver', 'multiplier': 1.5},
            {'name': 'Gold', 'multiplier': 2.0},
            {'name': 'Diamond', 'multiplier': 3.0},
        ]
        for t in tiers:
            AchievementTier.objects.get_or_create(name=t['name'], defaults={'multiplier': t['multiplier']})

        self.stdout.write(f'Created {len(badges)} Badges, 4 Achievement Categories, and 4 Achievement Tiers')

    def _seed_study_groups(self, admin, course):
        groups = [
            {'name': 'Computer Science Study Group', 'description': 'For BCS and IT students', 'privacy': 'public'},
            {'name': 'Business Management Club', 'description': 'BBM and BCOM students welcome', 'privacy': 'public'},
            {'name': 'Accounting Finals Prep', 'description': 'Prepare for accounting exams together', 'privacy': 'private'},
            {'name': 'Statistics Help Desk', 'description': 'Help with stats assignments', 'privacy': 'public'},
        ]

        for g in groups:
            StudyGroup.objects.get_or_create(
                name=g['name'],
                defaults={
                    'description': g['description'],
                    'privacy': g['privacy'],
                    'creator': admin,
                    'course': course,
                }
            )
        self.stdout.write(f'Created {len(groups)} Study Groups')

    def _print_summary(self):
        self.stdout.write('\n=== DATABASE SUMMARY ===')
        self.stdout.write(f'Users: {User.objects.count()}')
        self.stdout.write(f'Faculties: {Faculty.objects.count()}')
        self.stdout.write(f'Departments: {Department.objects.count()}')
        self.stdout.write(f'Courses: {Course.objects.count()}')
        self.stdout.write(f'Units: {Unit.objects.count()}')
        self.stdout.write(f'Resources: {Resource.objects.count()}')
        self.stdout.write(f'Announcements: {Announcement.objects.count()}')
        self.stdout.write(f'Study Groups: {StudyGroup.objects.count()}')
        self.stdout.write(f'Badges: {Badge.objects.count()}')
        self.stdout.write('========================\n')