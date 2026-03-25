# Microsoft Teams Integration for CampusHub

## Overview

This integration allows CampusHub to sync with Microsoft Teams to import assignments, grades, announcements, and enable Teams collaboration features.

## Features

### 1. Microsoft Graph API Integration
- OAuth2 authentication with Microsoft Graph API
- Sync Teams and channels
- Sync assignments from education classes
- Sync grades and submissions
- Sync team announcements

### 2. Teams Features
- Deep link to Teams channels
- Teams notification integration
- Teams meeting integration for study sessions

### 3. API Endpoints
- `POST /api/integrations/microsoft-teams/connect/` - Initiate OAuth flow
- `GET /api/integrations/microsoft-teams/oauth/callback/` - OAuth callback
- `POST /api/integrations/microsoft-teams/disconnect/` - Disconnect integration
- `GET /api/integrations/microsoft-teams/status/` - Get integration status
- `POST /api/integrations/microsoft-teams/sync/` - Trigger manual sync
- `GET /api/integrations/microsoft-teams/courses/` - Get synced Teams

## Configuration

Add the following to your `.env` file:

```env
# Microsoft Teams OAuth (can use same credentials as Microsoft OAuth)
MICROSOFT_OAUTH_CLIENT_ID=your-microsoft-client-id
MICROSOFT_OAUTH_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_TEAMS_REDIRECT_URI=http://localhost:8000/api/integrations/microsoft-teams/oauth/callback/
```

## Required Microsoft Graph API Permissions

The following delegated permissions are required:
- `User.Read` - Read user profile
- `User.ReadBasic.All` - Read basic user info
- `Team.ReadBasic.All` - Read teams
- `Channel.ReadBasic.All` - Read channels
- `ChannelMessage.Read.All` - Read messages
- `EducationAssignment.ReadWrite` - Read/write assignments
- `EducationSubmission.ReadWrite` - Read/write submissions
- `Calendars.Read` - Read calendars
- `OnlineMeetings.ReadWrite` - Create meetings

## Models

### MicrosoftTeamsAccount
Stores OAuth credentials and sync state for each user.

### SyncedTeam
Maps Microsoft Teams to CampusHub units.

### SyncedChannel
Stores synced channels from Teams.

### SyncedAssignment
Stores synced assignments from education classes.

### SyncedSubmission
Stores student submissions and grades.

### SyncedAnnouncements
Stores announcements from Teams channels.

### SyncState
Tracks sync history and results.

## Usage

1. User clicks "Connect to Microsoft Teams" in the frontend
2. Frontend calls `/api/integrations/microsoft-teams/connect/`
3. User is redirected to Microsoft login
4. After authentication, callback is processed
5. User's Teams data is synced automatically
6. User can view synced Teams and assignments in CampusHub

## Similar to Google Classroom

This integration follows the same pattern as the Google Classroom integration, making it easy to maintain consistency across both LMS integrations.