"""
Cloud Storage API Views for CampusHub
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CloudStorageAccount, CloudFile
from .services import CloudStorageService, GoogleDriveService, OneDriveService

logger = logging.getLogger(__name__)


VALID_PROVIDERS = {"google": "google_drive", "google_drive": "google_drive", "gdrive": "google_drive", "onedrive": "onedrive", "microsoft": "onedrive"}


def normalize_provider(raw: str):
    provider = VALID_PROVIDERS.get(str(raw or "").lower())
    if not provider:
        raise ValueError("Invalid provider")
    return provider


class CloudStorageStatusView(APIView):
    """Check if cloud storage is connected"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
            return Response({
                'connected': True,
                'email': account.email,
                'display_name': account.display_name,
            })
        except CloudStorageAccount.DoesNotExist:
            return Response({'connected': False})


class CloudStorageAccountView(APIView):
    """Get connected cloud storage account info"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
            return Response({
                'id': str(account.id),
                'provider': account.provider,
                'email': account.email,
                'display_name': account.display_name,
                'avatar_url': account.avatar_url,
                'connected': True,
                'last_sync': account.last_sync,
                'storage_used': account.storage_used,
                'storage_total': account.storage_total,
            })
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)


class CloudStorageConnectView(APIView):
    """Initiate OAuth connection to cloud storage"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        redirect_uri = request.data.get('redirect_uri')
        
        if not redirect_uri:
            return Response({'error': 'redirect_uri is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if provider == 'google_drive':
            auth_url = GoogleDriveService.get_authorization_url(redirect_uri)
            return Response({'authUrl': auth_url})
        elif provider == 'onedrive':
            auth_url = OneDriveService.get_authorization_url(redirect_uri)
            return Response({'authUrl': auth_url})
        else:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)


class CloudStorageOAuthCallbackView(APIView):
    """Handle OAuth callback from cloud storage"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        code = request.data.get('code')
        redirect_uri = request.data.get('redirect_uri')
        
        if not code or not redirect_uri:
            return Response({'error': 'code and redirect_uri are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            if provider == 'google_drive':
                account = CloudStorageService.connect_google_drive(request.user, code, redirect_uri)
            elif provider == 'onedrive':
                account = CloudStorageService.connect_onedrive(request.user, code, redirect_uri)
            else:
                return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'success': True,
                'account': {
                    'id': str(account.id),
                    'provider': account.provider,
                    'email': account.email,
                    'display_name': account.display_name,
                }
            })
        except Exception as e:
            logger.error(f"Cloud storage connection failed: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CloudStorageDisconnectView(APIView):
    """Disconnect cloud storage account"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
            CloudStorageService.disconnect(account)
            return Response({'success': True})
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)


class CloudStorageFilesView(APIView):
    """List files from cloud storage"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        folder_id = request.query_params.get('folder_id')
        page_token = request.query_params.get('page_token')
        
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            token = CloudStorageService.get_or_refresh_token(account)
            
            files = []
            next_page = None

            if provider == 'google_drive':
                result = GoogleDriveService.list_files(token, folder_id, page_token)
                next_page = result.get('nextPageToken')
                for f in result.get('files', []):
                    files.append({
                        'id': f['id'],
                        'name': f['name'],
                        'mimeType': f.get('mimeType', ''),
                        'size': int(f.get('size', 0)),
                        'modifiedTime': f.get('modifiedTime', ''),
                        'webUrl': f.get('webViewLink', ''),
                        'downloadUrl': f.get('webContentLink', ''),
                        'isFolder': f.get('mimeType') == 'application/vnd.google-apps.folder',
                    })
            else:
                result = OneDriveService.list_files(token, folder_id, page_token)
                next_page = result.get('@odata.nextLink') or result.get('nextLink') or result.get('nextPageToken')
                for f in result.get('value', []):
                    files.append({
                        'id': f['id'],
                        'name': f['name'],
                        'mimeType': f.get('file', {}).get('mimeType', ''),
                        'size': int(f.get('size', 0)),
                        'modifiedTime': f.get('lastModifiedDateTime', ''),
                        'webUrl': f.get('webUrl', ''),
                        'downloadUrl': f.get('@microsoft.graph.downloadUrl', ''),
                        'isFolder': 'folder' in f,
                    })

            return Response({
                'files': files,
                'nextPageToken': next_page,
            })
        except Exception as e:
            logger.error(f"Failed to list cloud files: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CloudStorageFoldersView(APIView):
    """List folders from cloud storage"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        parent_id = request.query_params.get('parent_id')
        
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            token = CloudStorageService.get_or_refresh_token(account)
            
            if provider == 'google_drive':
                folders = GoogleDriveService.list_folders(token, parent_id)
            else:
                folders = OneDriveService.list_folders(token, parent_id)
            
            return Response({'folders': folders})
        except Exception as e:
            logger.error(f"Failed to list cloud folders: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CloudStorageDownloadView(APIView):
    """Get download URL for a cloud file"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider, file_id):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            result = CloudStorageService.import_file(account, file_id)
            return Response(result)
        except Exception as e:
            logger.error(f"Failed to download cloud file: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CloudStorageStorageView(APIView):
    """Get storage quota information"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'provider': provider, 'storage_used': 0, 'storage_total': 0, 'connected': False})
        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
        except CloudStorageAccount.DoesNotExist:
            return Response({
                'provider': provider,
                'storage_used': 0,
                'storage_total': 0,
                'connected': False,
            })
        
        # Try to refresh storage info
        try:
            token = CloudStorageService.get_or_refresh_token(account)
            
            if provider == 'google_drive':
                storage_info = GoogleDriveService.get_storage_info(token)
            else:
                storage_info = OneDriveService.get_storage_info(token)
            
            account.storage_used = storage_info.get('storage_used', 0)
            account.storage_total = storage_info.get('storage_total', 0)
            account.save(update_fields=['storage_used', 'storage_total', 'updated_at'])
        except Exception as e:
            logger.warning(f"Failed to refresh storage info: {str(e)}")
        
        return Response({
            'provider': provider,
            'storage_used': account.storage_used,
            'storage_total': account.storage_total,
            'connected': True,
        })


class CloudAccountsListView(APIView):
    """Get all connected cloud storage accounts"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        accounts = CloudStorageAccount.objects.filter(
            user=request.user,
            is_active=True
        )
        
        return Response({
            'accounts': [
                {
                    'id': str(a.id),
                    'provider': a.provider,
                    'email': a.email,
                    'display_name': a.display_name,
                    'avatar_url': a.avatar_url,
                    'connected': True,
                    'last_sync': a.last_sync,
                }
                for a in accounts
            ]
        })


class CloudStorageSyncView(APIView):
    """Trigger a sync operation with the provider"""
    permission_classes = [IsAuthenticated]

    def post(self, request, provider):
        try:
            provider = normalize_provider(provider)
        except ValueError:
            return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = CloudStorageAccount.objects.get(
                user=request.user,
                provider=provider,
                is_active=True
            )
        except CloudStorageAccount.DoesNotExist:
            return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = CloudStorageService.sync_account(account)
            return Response(result)
        except Exception as e:
            logger.error(f"Cloud sync failed: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cloud_storage_import(request, provider):
    """Import a file from cloud storage"""
    try:
        provider = normalize_provider(provider)
    except ValueError:
        return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
    file_id = request.data.get('file_id')
    target_library_id = request.data.get('target_library_id')
    
    if not file_id:
        return Response({'error': 'file_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        account = CloudStorageAccount.objects.get(
            user=request.user,
            provider=provider,
            is_active=True
        )
    except CloudStorageAccount.DoesNotExist:
        return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        result = CloudStorageService.import_file(account, file_id, target_library_id)
        return Response(result)
    except Exception as e:
        logger.error(f"Failed to import cloud file: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cloud_storage_export(request, provider):
    """Export a resource to cloud storage"""
    try:
        provider = normalize_provider(provider)
    except ValueError:
        return Response({'error': 'Invalid provider'}, status=status.HTTP_400_BAD_REQUEST)
    resource_id = request.data.get('resource_id')
    folder_id = request.data.get('folder_id')
    
    if not resource_id:
        return Response({'error': 'resource_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        account = CloudStorageAccount.objects.get(
            user=request.user,
            provider=provider,
            is_active=True
        )
    except CloudStorageAccount.DoesNotExist:
        return Response({'error': 'Account not connected'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get resource from resources app
    from apps.resources.models import Resource
    try:
        resource = Resource.objects.get(id=resource_id, user=request.user)
    except Resource.DoesNotExist:
        return Response({'error': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)
    
    try:
        result = CloudStorageService.export_file(account, resource, folder_id)
        return Response(result)
    except Exception as e:
        logger.error(f"Failed to export to cloud: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
