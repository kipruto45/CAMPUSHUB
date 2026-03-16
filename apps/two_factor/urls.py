from django.urls import path

from . import views

app_name = "two_factor"

urlpatterns = [
    path("status/", views.two_factor_status, name="two-factor-status"),
    path("setup/", views.two_factor_setup, name="two-factor-setup"),
    path("enable/", views.two_factor_enable, name="two-factor-enable"),
    path("disable/", views.two_factor_disable, name="two-factor-disable"),
    path("recovery-codes/", views.two_factor_recovery_codes, name="two-factor-recovery-codes"),
]
