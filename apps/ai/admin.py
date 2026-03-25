"""
AI App Admin Configuration
"""

from django.contrib import admin

from apps.ai.models import StudyGoal, StudyGoalMilestone, GoalReminder


@admin.register(StudyGoal)
class StudyGoalAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'goal_type', 'status', 'priority', 'progress', 'target_date']
    list_filter = ['goal_type', 'status', 'priority', 'is_auto_generated']
    search_fields = ['title', 'description', 'user__email']
    readonly_fields = ['created_at', 'updated_at', 'completed_at']
    date_hierarchy = 'target_date'
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'title', 'description', 'goal_type', 'status', 'priority')
        }),
        ('Targets', {
            'fields': ('target_hours', 'target_topics', 'target_resources', 'course', 'unit')
        }),
        ('Progress', {
            'fields': ('progress', 'completed_hours', 'completed_topics')
        }),
        ('AI Analysis', {
            'fields': ('weak_areas', 'ai_recommendations')
        }),
        ('Dates', {
            'fields': ('start_date', 'target_date', 'completed_at', 'created_at', 'updated_at')
        }),
        ('Metadata', {
            'fields': ('is_auto_generated', 'generation_context'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StudyGoalMilestone)
class StudyGoalMilestoneAdmin(admin.ModelAdmin):
    list_display = ['title', 'study_goal', 'milestone_type', 'due_date', 'is_completed', 'progress']
    list_filter = ['milestone_type', 'is_completed']
    search_fields = ['title', 'study_goal__title']
    date_hierarchy = 'due_date'


@admin.register(GoalReminder)
class GoalReminderAdmin(admin.ModelAdmin):
    list_display = ['study_goal', 'reminder_type', 'scheduled_at', 'is_sent']
    list_filter = ['reminder_type', 'is_sent']
    search_fields = ['study_goal__title', 'message']
    date_hierarchy = 'scheduled_at'
    readonly_fields = ['created_at', 'updated_at', 'sent_at']