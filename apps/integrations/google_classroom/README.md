# Google Classroom Integration

This module provides integration with Google Classroom API for syncing courses, assignments, announcements, and grades.

## Features

- OAuth2 authentication with Google Classroom API
- Sync courses from Google Classroom
- Sync assignments and due dates
- Sync course announcements
- Sync student submissions and grades
- Automatic token refresh
- Scheduled periodic sync

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/integrations/google-classroom/connect/` | GET | Initiate OAuth2 flow |
| `/api/v1/integrations/google-classroom/oauth/callback/` | GET | OAuth2 callback handler |
| `/api/v1/integrations/google-classroom/disconnect/` | POST | Disconnect account |
| `/api/v1/integrations/google-classroom/status/` | GET | Get integration status |
| `/api/v1/integrations/google-classroom/sync/` | POST | Trigger manual sync |
| `/api/v1/integrations/google-classroom/courses/` | GET | List synced courses |
| `/api/v1/integrations/google-classroom/courses/<id>/` | GET | Get course details |

## Required Google API Scopes

- `https://www.googleapis.com/auth/classroom.courses.readonly`
- `https://www.googleapis.com/auth/classroom.coursework.students.readonly`
- `https://www.googleapis.com/auth/classroom.rosters.readonly`
- `https://www.googleapis.com/auth/classroom.announcements.readonly`
- `https://www.googleapis.com/auth/userinfo.email`
- `https://www.googleapis.com/auth/userinfo.profile`

## Configuration

Add the following to your `.env` file:

```env
# Google OAuth2
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_CLASSROOM_REDIRECT_URI=https://your-domain.com/api/v1/integrations/google-classroom/oauth/callback/
```

## Celery Tasks

The following periodic tasks are available:

- `google-classroom-sync-all` - Sync all connected accounts hourly
- `google-classroom-refresh-tokens` - Refresh expired tokens every 30 minutes

## Models

- `GoogleClassroomAccount` - Stores OAuth credentials and sync state
- `SyncedCourse` - Synced course data from Google Classroom
- `SyncedAssignment` - Synced assignment data
- `SyncedSubmission` - Synced student submissions and grades
- `SyncedAnnouncement` - Synced course announcements
- `SyncState` - History of sync operations