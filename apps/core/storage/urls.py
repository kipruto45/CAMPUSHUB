from django.urls import path

from . import views

app_name = "storage"

urlpatterns = [
    path("public/<path:path>/", views.serve_public_file, name="serve_public_file"),
    path("private/<path:path>/", views.serve_private_file, name="serve_private_file"),
    path("sign/", views.get_signed_url, name="get_signed_url"),
    path("quota/", views.check_storage_quota, name="check_storage_quota"),
    path("validate/", views.validate_upload, name="validate_upload"),
    path("upload/init/", views.initiate_upload, name="initiate_upload"),
    path("upload/complete/", views.complete_upload, name="complete_upload"),
    path("upgrade-requests/", views.request_storage_upgrade, name="storage-upgrade-request"),
]
