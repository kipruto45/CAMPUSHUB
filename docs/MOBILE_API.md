# CampusHub Mobile API Documentation

## Overview

The CampusHub Mobile API provides a RESTful interface for building iOS and Android applications. All endpoints return JSON and support JWT authentication.

### Base URL
```
Production: https://api.campushub.com
Development: http://localhost:8000
```

For the Expo mobile app, set:
```
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

Platform notes:
- Android emulator: `http://10.0.2.2:8000/api`
- iOS simulator: `http://127.0.0.1:8000/api`
- Physical phone: `http://<your-lan-ip>:8000/api`

### API Info Endpoint
Get API configuration and feature flags:
```
GET /api/mobile/info/
```

### Standard Response Headers
- `X-Request-ID`: unique backend request id for tracing/log correlation
- `X-API-Version`: current mobile API contract version
- `X-Idempotent-Replay`: present on idempotent write endpoints (`true|false`)

---

## Authentication

### Register
```
POST /api/mobile/register/
Content-Type: application/json

{
  "email": "user@university.edu",
  "password": "securepassword123",
  "first_name": "John",
  "last_name": "Doe",
  "registration_number": "REG/123456"
}

Response:
{
  "success": true,
  "data": {
    "user_id": 1,
    "email": "user@university.edu",
    "message": "Registration successful"
  }
}
```

### Login
```
POST /api/mobile/login/
Content-Type: application/json

{
  "email": "user@university.edu",
  "password": "securepassword123",
  "device_token": "firebase_token_xxx"  // Optional
}

Response:
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhb...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhb...",
    "expires_in": 3600,
    "user": {
      "id": 1,
      "email": "user@university.edu",
      "full_name": "John Doe",
      "profile_image": "https://...",
      "course_name": "Computer Science",
      "year_of_study": 2,
      "is_verified": true
    }
  }
}
```

### Refresh Token
```
POST /api/mobile/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhb..."
}

Response:
{
  "success": true,
  "data": {
    "access_token": "new_access_token",
    "refresh_token": "new_refresh_token",
    "expires_in": 3600
  }
}
```

### Logout
```
POST /api/mobile/logout/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "device_token": "firebase_token_xxx"  // Optional
}

Response:
{
  "success": true,
  "message": "Logged out successfully"
}
```

---

## Resources

### List Resources
```
GET /api/mobile/resources/
Authorization: Bearer <access_token>

Query Parameters:
- type: notes|past_paper|assignment|book|slides|tutorial
- course: Course ID
- unit: Unit ID
- search: Search query
- page: Page number (default: 1)
- limit: Items per page (default: 20, max: 50)
- sort: newest|oldest|popular|downloads|rating|title

Response:
{
  "success": true,
  "data": {
    "resources": [
      {
        "id": 1,
        "title": "Introduction to Algorithms",
        "description": "Complete notes for...",
        "file_type": "notes",
        "file_size": 2048576,
        "thumbnail": "https://...",
        "uploaded_by": "Jane Smith",
        "course_name": "Computer Science",
        "unit_name": "CS201",
        "download_count": 150,
        "view_count": 320,
        "average_rating": 4.5,
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 150,
      "pages": 8
    },
    "sort": "newest"
  }
}
```

### Resource Detail
```
GET /api/mobile/resources/<id>/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Introduction to Algorithms",
    "description": "Complete notes...",
    "resource_type": "notes",
    "file_type": "application/pdf",
    "file_size": 2048576,
    "thumbnail": "https://...",
    "file_url": "https://...",
    "uploaded_by": "Jane Smith",
    "course_name": "Computer Science",
    "unit_name": "CS201",
    "download_count": 150,
    "view_count": 320,
    "average_rating": 4.5,
    "created_at": "2024-01-15T10:30:00Z",
    "is_bookmarked": true,
    "is_favorited": false
  }
}
```

### Upload Resource
```
POST /api/mobile/resources/upload/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data

Required metadata fields:
- title (auto-filled from filename when omitted)
- file
- resource_type
- faculty
- department
- course
- unit
- semester
- year_of_study

Response:
{
  "success": true,
  "message": "Resource uploaded and submitted for review.",
  "data": {
    "resource": {...},
    "status": "pending"
  }
}
```

### Toggle Bookmark
```
POST /api/mobile/resources/<id>/bookmark/
Authorization: Bearer <access_token>
X-Idempotency-Key: <unique-client-key>  // optional
```

### Toggle Favorite
```
POST /api/mobile/resources/<id>/favorite/
Authorization: Bearer <access_token>
X-Idempotency-Key: <unique-client-key>  // optional
```

### Download Resource
```
POST /api/mobile/resources/<id>/download/
Authorization: Bearer <access_token>
X-Idempotency-Key: <unique-client-key>  // recommended

Response:
{
  "success": true,
  "data": {
    "download_id": "uuid",
    "resource_id": "uuid",
    "resource_title": "Data Structures Notes",
    "file_name": "data_structures_notes.pdf",
    "file_url": "https://..."
  }
}
```

### Save Public Resource To Library
```
POST /api/mobile/resources/<id>/save-to-library/
Authorization: Bearer <access_token>
X-Idempotency-Key: <unique-client-key>  // optional

Optional body:
{
  "folder_id": "uuid"
}
```

### Bookmarks & Favorites Lists
```
GET /api/mobile/bookmarks/
GET /api/mobile/favorites/
Authorization: Bearer <access_token>
```

### Personal Library Endpoints
```
GET /api/mobile/library/summary/
GET /api/mobile/library/files/?page=1&limit=20&search=algo&folder=<uuid>
GET /api/mobile/library/folders/?parent=root
Authorization: Bearer <access_token>
```

---

## Dashboard

### Get Dashboard
```
GET /api/mobile/dashboard/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "stats": {
      "total_uploads": 5,
      "total_downloads": 42,
      "total_bookmarks": 12,
      "total_favorites": 3
    },
    "recent_resources": [...],
    "announcements": [
      {
        "id": 1,
        "title": "Exam Schedule",
        "message": "The mid-term exam schedule...",
        "type": "announcement",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ]
  }
}
```

---

## Notifications

### List Notifications
```
GET /api/mobile/notifications/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "notifications": [
      {
        "id": 1,
        "title": "Resource Approved",
        "message": "Your uploaded resource has been approved",
        "type": "resource_approved",
        "is_read": false,
        "link": "/resources/123",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "unread_count": 3,
    "pagination": {...}
  }
}
```

### Mark as Read
```
POST /api/mobile/notifications/<id>/read/
Authorization: Bearer <access_token>
X-Idempotency-Key: <unique-client-key>  // optional but recommended for retries

Response:
{
  "success": true,
  "message": "Notification marked as read"
}
```

---

## Device & Push Notifications

### Register Device
```
POST /api/mobile/device/register/
Authorization: Bearer <access_token>
Content-Type: application/json
X-Idempotency-Key: <unique-client-key>  // optional but recommended for retries

{
  "device_token": "firebase_token_xxx",
  "device_type": "android",  // android, ios, web
  "device_name": "Samsung Galaxy S21",
  "device_model": "SM-G991B",
  "app_version": "1.0.0"
}

Response:
{
  "success": true,
  "message": "Device registered"
}
```

### Subscribe to Topic
```
POST /api/mobile/topic/subscribe/
Authorization: Bearer <access_token>
Content-Type: application/json
X-Idempotency-Key: <unique-client-key>  // optional but recommended for retries

{
  "topic": "announcements",  // announcements, resources, updates, all
  "device_token": "firebase_token_xxx"
}

Response:
{
  "success": true,
  "message": "Subscribed to announcements"
}
```

### Unsubscribe from Topic
```
POST /api/mobile/topic/unsubscribe/
Authorization: Bearer <access_token>
Content-Type: application/json
X-Idempotency-Key: <unique-client-key>  // optional but recommended for retries

{
  "topic": "announcements",
  "device_token": "firebase_token_xxx"
}

Response:
{
  "success": true,
  "message": "Unsubscribed from announcements"
}
```

---

## Courses & Units

### List Courses
```
GET /api/mobile/courses/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "courses": [
      {"id": 1, "name": "Computer Science", "code": "CS"},
      {"id": 2, "name": "Engineering", "code": "ENG"}
    ]
  }
}
```

### List Units
```
GET /api/mobile/courses/<id>/units/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "units": [
      {"id": 1, "name": "Data Structures", "code": "CS201"},
      {"id": 2, "name": "Algorithms", "code": "CS202"}
    ]
  }
}
```

### List Faculties
```
GET /api/mobile/faculties/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "faculties": [
      {"id": 1, "name": "Faculty of Science"},
      {"id": 2, "name": "Faculty of Engineering"}
    ]
  }
}
```

---

## Offline Support

### Sync Data
```
GET /api/mobile/sync/
Authorization: Bearer <access_token>
Query Parameters:
- since: ISO timestamp (optional)

Response:
{
  "success": true,
  "data": {
    "user": {...},
    "bookmarked_resources": [1, 5, 10],
    "favorite_resources": [3, 7],
    "recent_resources": [...],
    "sync_timestamp": "2024-01-15T10:30:00Z"
  }
}
```

---

## Stats

### Get User Stats
```
GET /api/mobile/stats/
Authorization: Bearer <access_token>

Response:
{
  "success": true,
  "data": {
    "stats": {
      "total_uploads": 5,
      "total_downloads": 42,
      "total_bookmarks": 12,
      "total_favorites": 3,
      "storage_used": 52428800,
      "storage_limit": 104857600
    }
  }
}
```

---

## Error Responses

### Error Format
```json
{
  "success": false,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE"
  }
}
```

### Common Error Codes
- `VALIDATION_ERROR` - Invalid input data
- `AUTHENTICATION_FAILED` - Invalid credentials
- `NOT_FOUND` - Resource not found
- `RATE_LIMIT_EXCEEDED` - Too many requests
- `PERMISSION_DENIED` - Access denied

### HTTP Status Codes
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Server Error

---

## WebSocket Connections

### Notifications WebSocket
```
ws://api.campushub.com/ws/notifications/
```

**Authentication:** Pass JWT token in connection query params.

**Events received:**
- `notification` - New notification
- `notification_read` - Notification marked as read
- `notification_deleted` - Notification deleted

### Typing Indicators
```
ws://api.campushub.com/ws/typing/
```

**Send events:**
```json
{"type": "typing_start", "room": "resource_123", "room_type": "resource"}
{"type": "typing_stop", "room": "resource_123", "room_type": "resource"}
```

### Online Presence
```
ws://api.campushub.com/ws/presence/
```

---

## Deep Linking

### URL Schemes

**Custom URL Scheme (iOS/Android):**
```
campushub://resources/123
campushub://resources/123/download
campushub://courses/1
campushub://profile/5
campushub://search?q=python
campushub://auth/login
campushub://auth/register
```

**Universal Links (HTTPS):**
```
https://campushub.com/resources/123
https://campushub.com/courses/1
https://campushub.com/profile/5
https://campushub.com/search?q=python
```

### Mobile Navigation Routes

| URL | Screen | Params |
|-----|--------|--------|
| `/resources/<id>` | ResourceDetail | `{resourceId: "id"}` |
| `/courses/<id>` | CourseDetail | `{courseId: "id"}` |
| `/units/<id>` | UnitDetail | `{unitId: "id"}` |
| `/profile/<id>` | Profile | `{userId: "id"}` |
| `/search?q=<query>` | Search | `{query: "query"}` |
| `/auth/login` | Login | `{}` |
| `/auth/register` | Register | `{}` |

---

## Rate Limits

| Endpoint Type | Limit |
|---------------|-------|
| Auth (login/register) | 10/minute |
| API Calls (authenticated) | 200/hour |
| API Calls (anonymous) | 30/minute |
| Resource Uploads | 10/day |
| Resource Downloads | 100/hour |

---

## Push Notification Payloads

### Android (FCM)
```json
{
  "notification": {
    "title": "New Notification",
    "body": "Notification message"
  },
  "data": {
    "type": "resource_approved",
    "resource_id": "123"
  }
}
```

### iOS (APNs)
```json
{
  "aps": {
    "alert": {
      "title": "New Notification",
      "body": "Notification message"
    },
    "sound": "default",
    "badge": 1
  },
  "data": {
    "type": "resource_approved"
  }
}
```

---

## Best Practices

1. **Token Management**
   - Store tokens securely (use Keychain/Keystore)
   - Implement token refresh before expiration
   - Handle 401 responses by refreshing token

2. **Offline Support**
   - Use `/api/mobile/sync/` to cache data
   - Store user preferences locally
   - Queue actions when offline

3. **Push Notifications**
   - Register device on first app launch
   - Handle notification taps to navigate
   - Update badge count from notifications

4. **Deep Links**
   - Handle links when app is in background
   - Parse URL to get navigation target
   - Handle both custom scheme and universal links

5. **Error Handling**
   - Show user-friendly error messages
   - Log errors for debugging
   - Implement retry logic for network errors
