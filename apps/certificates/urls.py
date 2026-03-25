"""
URL configuration for certificates app.
"""

from django.urls import path

from .views import (
    CertificateDetailView,
    CertificateDownloadView,
    CertificateGenerateView,
    CertificateListCreateView,
    CertificateTypeListView,
    CertificateTemplateListView,
    CertificateVerifyView,
    UserCertificateListView,
)

app_name = "certificates"

urlpatterns = [
    # Certificate types and templates
    path("types/", CertificateTypeListView.as_view(), name="certificate-type-list"),
    path(
        "templates/",
        CertificateTemplateListView.as_view(),
        name="certificate-template-list",
    ),
    # Main certificate endpoints
    path("", CertificateListCreateView.as_view(), name="certificate-list-create"),
    path(
        "generate/",
        CertificateGenerateView.as_view(),
        name="certificate-generate",
    ),
    path(
        "verify/<str:unique_id>/",
        CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
    # Certificate detail and download
    path(
        "<str:unique_id>/",
        CertificateDetailView.as_view(),
        name="certificate-detail",
    ),
    path(
        "<str:unique_id>/download/",
        CertificateDownloadView.as_view(),
        name="certificate-download",
    ),
    # User certificates
    path(
        "user/<int:user_id>/",
        UserCertificateListView.as_view(),
        name="user-certificate-list",
    ),
]
