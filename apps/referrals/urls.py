"""
URL configuration for referral API.
"""

from django.urls import path

from . import views

app_name = "referrals"

urlpatterns = [
    path("code/", views.get_referral_code, name="referral_code"),
    path("stats/", views.get_referral_stats, name="referral_stats"),
    path("list/", views.get_referrals_list, name="referrals_list"),
    path("use/", views.use_referral_code, name="use_referral_code"),
    path("rewards/", views.get_reward_history, name="reward_history"),
    path("claim/", views.claim_referral_rewards, name="claim_rewards"),
]
