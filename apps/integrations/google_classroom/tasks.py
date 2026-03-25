"""
Celery tasks for Google Classroom sync.
"""

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=3)
def sync_all_google_classroom_accounts(self):
    """
    Periodic task to sync all Google Classroom accounts.
    This runs periodically to fetch new data from Google Classroom.
    """
    from .models import GoogleClassroomAccount, SyncState
    from .services import GoogleClassroomSyncService

    accounts = GoogleClassroomAccount.objects.filter(
        sync_status=GoogleClassroomAccount.SyncStatus.ACTIVE
    )

    results = []
    for account in accounts:
        try:
            sync_service = GoogleClassroomSyncService(account)
            sync_state = sync_service.sync_all(sync_type=SyncState.SyncType.SCHEDULED)
            results.append({
                "account_id": str(account.id),
                "email": account.email,
                "status": "success",
                "sync_state_id": str(sync_state.id),
            })
        except Exception as exc:
            results.append({
                "account_id": str(account.id),
                "email": account.email,
                "status": "failed",
                "error": str(exc),
            })
            # Update account sync status
            account.sync_status = GoogleClassroomAccount.SyncStatus.ERROR
            account.last_error = str(exc)
            account.save(update_fields=["sync_status", "last_error", "updated_at"])

    return {
        "total_accounts": accounts.count(),
        "results": results,
        "timestamp": timezone.now().isoformat(),
    }


@shared_task(bind=True, max_retries=3)
def sync_single_google_classroom_account(self, account_id):
    """
    Task to sync a single Google Classroom account.
    Can be triggered manually or by webhook.
    """
    from .models import GoogleClassroomAccount, SyncState
    from .services import GoogleClassroomSyncService

    try:
        account = GoogleClassroomAccount.objects.get(id=account_id)
    except GoogleClassroomAccount.DoesNotExist:
        return {"error": f"Account {account_id} not found"}

    sync_service = GoogleClassroomSyncService(account)
    sync_state = sync_service.sync_all(sync_type=SyncState.SyncType.MANUAL)

    return {
        "account_id": str(account.id),
        "email": account.email,
        "status": "success",
        "sync_state_id": str(sync_state.id),
    }


@shared_task
def refresh_expired_tokens():
    """
    Periodic task to refresh expired Google OAuth tokens.
    """
    from .models import GoogleClassroomAccount
    from .services import GoogleClassroomOAuthService

    now = timezone.now()
    accounts = GoogleClassroomAccount.objects.filter(
        token_expires_at__lte=now,
        sync_status=GoogleClassroomAccount.SyncStatus.ACTIVE,
    )

    results = []
    for account in accounts:
        try:
            # Refresh the token
            new_tokens = GoogleClassroomOAuthService.refresh_access_token(
                account.refresh_token
            )

            # Calculate new expiry
            expires_in = new_tokens.get("expires_in", 3600)
            token_expires_at = now + timezone.timedelta(seconds=expires_in)

            # Update account
            account.access_token = new_tokens["access_token"]
            if "refresh_token" in new_tokens:
                account.refresh_token = new_tokens["refresh_token"]
            account.token_expires_at = token_expires_at
            account.save(
                update_fields=[
                    "access_token",
                    "refresh_token",
                    "token_expires_at",
                    "updated_at",
                ]
            )

            results.append({
                "account_id": str(account.id),
                "email": account.email,
                "status": "refreshed",
            })
        except Exception as exc:
            results.append({
                "account_id": str(account.id),
                "email": account.email,
                "status": "failed",
                "error": str(exc),
            })
            account.last_error = f"Token refresh failed: {str(exc)}"
            account.save(update_fields=["last_error", "updated_at"])

    return {
        "total_refreshed": accounts.count(),
        "results": results,
        "timestamp": now.isoformat(),
    }
