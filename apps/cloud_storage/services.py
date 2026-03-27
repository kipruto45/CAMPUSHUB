"""
Cloud Storage Services for CampusHub
Google Drive and OneDrive integration services
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.utils import timezone

from .models import CloudStorageAccount, CloudFile, CloudImportHistory, CloudExportHistory

logger = logging.getLogger(__name__)


class GoogleDriveService:
    """Service for Google Drive API interactions"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
    ]
    
    AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    TOKEN_URL = 'https://oauth2.googleapis.com/token'
    API_BASE_URL = 'https://www.googleapis.com/drive/v3'

    @classmethod
    def _ensure_configured(cls) -> None:
        if not str(getattr(settings, 'GOOGLE_CLIENT_ID', '') or '').strip():
            raise ValueError('Google Drive is not configured right now.')
        if not str(getattr(settings, 'GOOGLE_CLIENT_SECRET', '') or '').strip():
            raise ValueError('Google Drive is not configured right now.')
    
    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        from urllib.parse import urlencode

        cls._ensure_configured()
        
        params = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(cls.SCOPES),
            'access_type': 'offline',
            'prompt': 'consent',
        }
        if state:
            params['state'] = state
            
        return f"{cls.AUTH_URL}?{urlencode(params)}"
    
    @classmethod
    def exchange_code_for_tokens(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        cls._ensure_configured()
        data = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(cls.TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        cls._ensure_configured()
        data = {
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }
        
        response = requests.post(cls.TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user profile information from Google"""
        response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def get_storage_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user's storage quota information"""
        response = requests.get(
            f'{cls.API_BASE_URL}/about',
            params={'fields': 'storageQuota'},
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        data = response.json()
        
        quota = data.get('storageQuota', {})
        return {
            'storage_used': int(quota.get('limit', 0)) - int(quota.get('quotaBytesUsedFree', 0)),
            'storage_total': int(quota.get('limit', 0)),
        }
    
    @classmethod
    def list_files(cls, access_token: str, folder_id: str = None, page_token: str = None) -> Dict[str, Any]:
        """List files in Google Drive"""
        params = {
            'pageSize': 100,
            'fields': 'nextPageToken,files(id,name,mimeType,size,modifiedTime,webViewLink,parents)',
        }
        
        if folder_id:
            params['q'] = f"'{folder_id}' in parents and trashed = false"
        else:
            params['q'] = "trashed = false and 'root' in parents"
            
        if page_token:
            params['pageToken'] = page_token
            
        response = requests.get(
            f'{cls.API_BASE_URL}/files',
            params=params,
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def list_folders(cls, access_token: str, parent_id: str = None) -> List[Dict[str, Any]]:
        """List folders in Google Drive"""
        params = {
            'pageSize': 100,
            'fields': 'files(id,name,mimeType)',
        }
        
        if parent_id:
            params['q'] = f"mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed = false"
        else:
            params['q'] = "mimeType='application/vnd.google-apps.folder' and trashed = false"
            
        response = requests.get(
            f'{cls.API_BASE_URL}/files',
            params=params,
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        
        data = response.json()
        return [
            {
                'id': f['id'],
                'name': f['name'],
                'path': f['name'],
            }
            for f in data.get('files', [])
            if f['mimeType'] == 'application/vnd.google-apps.folder'
        ]
    
    @classmethod
    def get_file_download_url(cls, access_token: str, file_id: str) -> str:
        """Get download URL for a file"""
        response = requests.get(
            f'{cls.API_BASE_URL}/files/{file_id}',
            params={'fields': 'webContentLink'},
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        data = response.json()
        return data.get('webContentLink')
    
    @classmethod
    def upload_file(cls, access_token: str, file_data: bytes, filename: str, parent_folder_id: str = None) -> Dict[str, Any]:
        """Upload a file to Google Drive"""
        import mimetypes
        
        mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        metadata = {
            'name': filename,
            'parents': [parent_folder_id] if parent_folder_id else ['root'],
        }
        
        import multipart
        from io import BytesIO
        
        # Create multipart request
        boundary = '-------314159265358979323846'
        delimiter = f"\r\n--{boundary}\r\n"
        close_delimiter = f"\r\n--{boundary}--"
        
        body = delimiter
        body += f'Content-Type: application/json; charset=UTF-8\r\n\r\n'
        body += str(metadata)
        body += delimiter
        body += f'Content-Type: {mime_type}\r\n\r\n'
        
        # Read file content
        file_content = file_data
        body += file_content.decode('utf-8') if isinstance(file_content, bytes) else file_content
        body += close_delimiter
        
        response = requests.post(
            f'{cls.API_BASE_URL}/upload',
            params={'uploadType': 'multipart'},
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': f'multipart/related; boundary={boundary}',
            },
            data=body.encode('utf-8')
        )
        response.raise_for_status()
        return response.json()


class OneDriveService:
    """Service for Microsoft OneDrive API interactions"""
    
    AUTH_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
    TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'
    API_BASE_URL = 'https://graph.microsoft.com/v1.0'
    
    SCOPES = ['Files.ReadWrite.All', 'User.Read']

    @classmethod
    def _ensure_configured(cls) -> None:
        if not str(getattr(settings, 'MICROSOFT_CLIENT_ID', '') or '').strip():
            raise ValueError('Microsoft cloud storage is not configured right now.')
        if not str(getattr(settings, 'MICROSOFT_CLIENT_SECRET', '') or '').strip():
            raise ValueError('Microsoft cloud storage is not configured right now.')
    
    @classmethod
    def get_authorization_url(cls, redirect_uri: str, state: str = None) -> str:
        """Generate OAuth authorization URL"""
        from urllib.parse import urlencode

        cls._ensure_configured()
        
        params = {
            'client_id': settings.MICROSOFT_CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(cls.SCOPES),
            'response_mode': 'query',
        }
        if state:
            params['state'] = state
            
        return f"{cls.AUTH_URL}?{urlencode(params)}"
    
    @classmethod
    def exchange_code_for_tokens(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access and refresh tokens"""
        cls._ensure_configured()
        data = {
            'client_id': settings.MICROSOFT_CLIENT_ID,
            'client_secret': settings.MICROSOFT_CLIENT_SECRET,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': redirect_uri,
            'scope': ' '.join(cls.SCOPES),
        }
        
        response = requests.post(cls.TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        cls._ensure_configured()
        data = {
            'client_id': settings.MICROSOFT_CLIENT_ID,
            'client_secret': settings.MICROSOFT_CLIENT_SECRET,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': ' '.join(cls.SCOPES),
        }
        
        response = requests.post(cls.TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def get_user_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user profile information from Microsoft Graph"""
        response = requests.get(
            f'{cls.API_BASE_URL}/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def get_storage_info(cls, access_token: str) -> Dict[str, Any]:
        """Get user's storage quota information"""
        response = requests.get(
            f'{cls.API_BASE_URL}/me/drive',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        response.raise_for_status()
        data = response.json()
        
        quota = data.get('quota', {})
        return {
            'storage_used': quota.get('used', 0),
            'storage_total': quota.get('total', 0),
        }
    
    @classmethod
    def list_files(cls, access_token: str, folder_id: str = None, page_token: str = None) -> Dict[str, Any]:
        """List files in OneDrive"""
        if folder_id:
            url = f"{cls.API_BASE_URL}/me/drive/items/{folder_id}/children"
        else:
            url = f"{cls.API_BASE_URL}/me/drive/root/children"
        
        params = {'$top': 100}
        if page_token:
            params['$skiptoken'] = page_token
            
        response = requests.get(url, params=params, headers={'Authorization': f'Bearer {access_token}'})
        response.raise_for_status()
        return response.json()
    
    @classmethod
    def list_folders(cls, access_token: str, parent_id: str = None) -> List[Dict[str, Any]]:
        """List folders in OneDrive"""
        if parent_id:
            url = f"{cls.API_BASE_URL}/me/drive/items/{parent_id}/children"
        else:
            url = f"{cls.API_BASE_URL}/me/drive/root/children"
        
        params = {'$filter': 'folder ne null', '$top': 100}
        
        response = requests.get(url, params=params, headers={'Authorization': f'Bearer {access_token}'})
        response.raise_for_status()
        
        data = response.json()
        return [
            {
                'id': f['id'],
                'name': f['name'],
                'path': f['parentReference']['path'].replace('/drive/root:', '') + '/' + f['name'] if f.get('parentReference') else f['name'],
            }
            for f in data.get('value', []) if 'folder' in f
        ]
    
    @classmethod
    def get_file_download_url(cls, access_token: str, file_id: str) -> str:
        """Get download URL for a file"""
        response = requests.get(
            f"{cls.API_BASE_URL}/me/drive/items/{file_id}/content",
            headers={'Authorization': f'Bearer {access_token}'},
            allow_redirects=False
        )
        response.raise_for_status()
        return response.headers.get('Location')


class CloudStorageService:
    """Unified cloud storage service for CampusHub"""
    
    @staticmethod
    def get_or_refresh_token(account: CloudStorageAccount) -> str:
        """Get valid access token, refreshing if necessary"""
        if account.is_token_expired:
            if account.provider == CloudStorageAccount.Provider.GOOGLE_DRIVE:
                token_data = GoogleDriveService.refresh_access_token(account.refresh_token)
            else:
                token_data = OneDriveService.refresh_access_token(account.refresh_token)
            
            account.access_token = token_data['access_token']
            if 'refresh_token' in token_data:
                account.refresh_token = token_data['refresh_token']
            if 'expires_in' in token_data:
                account.token_expires_at = timezone.now() + timedelta(seconds=token_data['expires_in'])
            account.save(update_fields=['access_token', 'refresh_token', 'token_expires_at', 'updated_at'])
        
        return account.access_token
    
    @staticmethod
    def connect_google_drive(user, code: str, redirect_uri: str) -> CloudStorageAccount:
        """Connect Google Drive account"""
        # Exchange code for tokens
        token_data = GoogleDriveService.exchange_code_for_tokens(code, redirect_uri)
        
        # Get user info
        user_info = GoogleDriveService.get_user_info(token_data['access_token'])
        
        # Get storage info
        storage_info = GoogleDriveService.get_storage_info(token_data['access_token'])
        
        # Create or update account
        account, created = CloudStorageAccount.objects.update_or_create(
            user=user,
            provider=CloudStorageAccount.Provider.GOOGLE_DRIVE,
            defaults={
                'provider_user_id': user_info['id'],
                'email': user_info.get('email', ''),
                'display_name': user_info.get('name', user_info.get('email', '')),
                'avatar_url': user_info.get('picture'),
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'token_expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                'storage_used': storage_info.get('storage_used', 0),
                'storage_total': storage_info.get('storage_total', 0),
                'is_active': True,
            }
        )
        
        return account
    
    @staticmethod
    def connect_onedrive(user, code: str, redirect_uri: str) -> CloudStorageAccount:
        """Connect OneDrive account"""
        # Exchange code for tokens
        token_data = OneDriveService.exchange_code_for_tokens(code, redirect_uri)
        
        # Get user info
        user_info = OneDriveService.get_user_info(token_data['access_token'])
        
        # Get storage info
        storage_info = OneDriveService.get_storage_info(token_data['access_token'])
        
        # Create or update account
        account, created = CloudStorageAccount.objects.update_or_create(
            user=user,
            provider=CloudStorageAccount.Provider.ONEDRIVE,
            defaults={
                'provider_user_id': user_info['id'],
                'email': user_info.get('mail', user_info.get('userPrincipalName', '')),
                'display_name': user_info.get('displayName', user_info.get('mail', '')),
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'token_expires_at': timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600)),
                'storage_used': storage_info.get('storage_used', 0),
                'storage_total': storage_info.get('storage_total', 0),
                'is_active': True,
            }
        )
        
        return account
    
    @staticmethod
    def disconnect(account: CloudStorageAccount):
        """Disconnect a cloud storage account"""
        account.is_active = False
        account.save(update_fields=['is_active', 'updated_at'])
    
    @staticmethod
    def import_file(account: CloudStorageAccount, file_id: str, target_library_id: str = None):
        """Import a file from cloud storage to CampusHub"""
        # This would integrate with the resources app
        # For now, return the file info for download
        token = CloudStorageService.get_or_refresh_token(account)
        
        if account.provider == CloudStorageAccount.Provider.GOOGLE_DRIVE:
            download_url = GoogleDriveService.get_file_download_url(token, file_id)
        else:
            download_url = OneDriveService.get_file_download_url(token, file_id)
        
        return {'download_url': download_url}
    
    @staticmethod
    def export_file(account: CloudStorageAccount, resource, folder_id: str = None):
        """Export a CampusHub resource to cloud storage"""
        token = CloudStorageService.get_or_refresh_token(account)
        
        # Get file data from CampusHub resource
        file_path = resource.file.path if resource.file else None
        if not file_path or not os.path.exists(file_path):
            raise ValueError("Resource file not found")
        
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        filename = resource.title + '.' + resource.file_extension
        
        if account.provider == CloudStorageAccount.Provider.GOOGLE_DRIVE:
            result = GoogleDriveService.upload_file(token, file_data, filename, folder_id)
        else:
            result = OneDriveService.upload_file(token, file_data, filename, folder_id)
        
        return {'cloud_file_id': result.get('id'), 'cloud_file_name': filename}

    @staticmethod
    def sync_account(account: CloudStorageAccount) -> Dict[str, Any]:
        """Placeholder sync operation that refreshes storage stats and marks last_sync."""
        token = CloudStorageService.get_or_refresh_token(account)
        stats = {}
        if account.provider == CloudStorageAccount.Provider.GOOGLE_DRIVE:
            stats = GoogleDriveService.get_storage_info(token)
        else:
            stats = OneDriveService.get_storage_info(token)

        account.storage_used = stats.get('storage_used', account.storage_used)
        account.storage_total = stats.get('storage_total', account.storage_total)
        account.last_sync = timezone.now()
        account.save(update_fields=['storage_used', 'storage_total', 'last_sync', 'updated_at'])

        return {
            'synced': 0,
            'errors': [],
            'storage_used': account.storage_used,
            'storage_total': account.storage_total,
            'last_sync': account.last_sync,
        }
