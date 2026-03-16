# CampusHub Mobile App - Comprehensive Specification

## Table of Contents

1. [Overview](#overview)
2. [Current Features](#current-features)
3. [Dashboard Specifications](#dashboard-specifications)
4. [Share Feature Specification](#share-feature-specification)
5. [7 Collaboration Features](#7-collaboration-features)
6. [UI/UX Improvements](#uiux-improvements)
7. [Backend API Requirements](#backend-api-requirements)

---

## Overview

CampusHub is a comprehensive university learning platform built with:
- **Frontend**: React Native + Expo + TypeScript
- **Backend**: Django REST Framework
- **Database**: PostgreSQL
- **Authentication**: JWT + OAuth

The app serves students, faculty, and administrators with features for sharing educational resources, collaboration, and personal library management.

---

## Current Features

### Implemented Features

1. **Authentication**
   - Email/password login
   - OAuth (Google, GitHub)
   - Two-factor authentication
   - Role-based access (student, faculty, admin)

2. **Resource Management**
   - Upload notes, books, slides, past papers, assignments, tutorials
   - Download resources
   - Bookmark and favorite resources
   - Rate and review resources

3. **Personal Library**
   - Private file storage
   - Folder organization
   - Collections/grouping

4. **Study Groups**
   - Create and join groups
   - Share resources within groups
   - Group discussions

5. **Recommendations**
   - Personalized resource suggestions
   - Trending resources
   - Category-based browsing

6. **Search**
   - Global search across all resources
   - Filter by type, course, faculty

7. **Notifications**
   - Push notifications
   - In-app notifications
   - Announcement system

---

## Dashboard Specifications

### Proposed Dashboard Structure

The dashboard should be the main control center with the following sections in order:

```
┌─────────────────────────────────┐
│ 1. Header                       │
│    - CampusHub Logo              │
│    - Greeting + Student Name     │
│    - Notifications Icon          │
│    - Profile Shortcut            │
├─────────────────────────────────┤
│ 2. Welcome / Hero Card           │
│    - Welcome message             │
│    - Quick action button         │
├─────────────────────────────────┤
│ 3. Global Search Bar              │
├─────────────────────────────────┤
│ 4. Quick Action Buttons          │
│    - Resources | Upload | Library│
│    - Saved | Favorites           │
├─────────────────────────────────┤
│ 5. Recently Uploaded Files ⭐ NEW │
│    - Horizontal scroll cards     │
│    - Show user's uploads        │
├─────────────────────────────────┤
│ 6. Continue Studying             │
│    - Recently opened resources  │
├─────────────────────────────────┤
│ 7. Recommended for You           │
│    - Personalized suggestions  │
├─────────────────────────────────┤
│ 8. Trending Resources            │
│    - Popular this week           │
├─────────────────────────────────┤
│ 9. Categories                    │
│    - Notes | Books | Papers     │
├─────────────────────────────────┤
│ 10. Saved / Favorites Preview   │
├─────────────────────────────────┤
│ 11. Personal Library Preview    │
├─────────────────────────────────┤
│ 12. Collections Preview         │
├─────────────────────────────────┤
│ 13. Announcements               │
├─────────────────────────────────┤
│ 14. Notifications Preview       │
├─────────────────────────────────┤
│ 15. Recent Activity             │
├─────────────────────────────────┤
│ 16. Storage Summary             │
└─────────────────────────────────┘
```

### Recently Uploaded Files Section (NEW)

**Purpose**: Show students their own recently uploaded resources

**Data Fields**:
- Resource title
- Resource type (icon)
- Upload date
- Status (approved/pending/rejected)
- View count
- Download count

**UI Design**:
- Horizontal scrollable list
- Card shows thumbnail, title, type badge
- Tap to view resource details

**API Endpoint**:
```
GET /api/resources/my-uploads/
Parameters:
  - limit: int (default 10)
  - offset: int (default 0)
```

---

## Share Feature Specification

### 1. Share Icon Placement

| Location | Icon Position | Action |
|----------|--------------|--------|
| Resource Cards | Right side of action row | Opens share sheet |
| Resource Details | Top right header | Opens share sheet |
| Study Group Posts | After download button | Quick share |
| Library Files | Action menu | Share file |

### 2. Share Options

```
┌─────────────────────────────────┐
│      Share Resource             │
├─────────────────────────────────┤
│  [Resource Preview Card]        │
│   - Title                       │
│   - Course Code                 │
│   - Type                        │
├─────────────────────────────────┤
│  📋 Copy Link                   │
│     Copy shareable URL          │
│                                  │
│  📤 Share via Device             │
│     WhatsApp, Telegram, Email   │
│                                  │
│  👤 Send to Student              │
│     In-app sharing              │
│                                  │
│  👥 Share to Study Group        │
│     Select group to share       │
└─────────────────────────────────┘
```

### 3. Backend Implementation

**Model: ResourceShareEvent**
```python
class ResourceShareEvent(models.Model):
    SHARE_METHODS = [
        ('copy_link', 'Copy Link'),
        ('native_share', 'Native Share'),
        ('send_to_student', 'Send to Student'),
        ('share_to_group', 'Share to Study Group'),
    ]
    
    resource = models.ForeignKey('resources.Resource', on_delete=models.CASCADE)
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    receiver = models.ForeignKey('accounts.User', null=True, on_delete=models.CASCADE)
    group = models.ForeignKey('social.StudyGroup', null=True, on_delete=models.CASCADE)
    share_method = models.CharField(max_length=20, choices=SHARE_METHODS)
    created_at = models.DateTimeField(auto_now_add=True)
```

**API Endpoints**:
```
POST /api/resources/{id}/share/
POST /api/resources/{id}/share-to-student/
POST /api/resources/{id}/share-to-group/
GET /api/resources/{id}/share-count/
```

### 4. Notifications

When resource is shared:
- **Send to Student**: Notification with "User shared X with you"
- **Share to Group**: Notification to all group members

### 5. Activity Tracking

Add to Recent Activity:
- "You shared [Resource Name]"
- "[User] shared [Resource Name] with you"

---

## 7 Collaboration Features

### Feature 1: Real-time Study Groups

**Description**: Enhanced study groups with real-time messaging and resource sharing

**Components**:
- Group chat with message history
- File sharing within groups
- Member online status
- Typing indicators
- Read receipts

**Backend**:
- WebSocket for real-time messaging
- Group message model
- File attachment support

### Feature 2: Collaborative Notes

**Description**: Allow multiple students to edit notes together

**Components**:
- Rich text editor
- Real-time collaborative editing
- Version history
- Comments on notes

**Backend**:
- Operational Transformation or CRDT for conflict resolution
- Note collaboration model

### Feature 3: Resource Requests

**Description**: Students can request specific resources

**Components**:
- Request form (course, topic, type)
- Upvote system for popular requests
- Notification when request is fulfilled
- Track request status

**Backend**:
- ResourceRequest model
- Upvote/interest tracking

### Feature 4: Study Sessions / Pomodoro

**Description**: Built-in study timer for focused learning

**Components**:
- Pomodoro timer (25/5 min)
- Study streak tracking
- Session history
- Break reminders

**Backend**:
- StudySession model
- Streak calculation

### Feature 5: Peer Tutoring Matching

**Description**: Match students with tutors based on subjects

**Components**:
- Tutor profiles
- Subject expertise
- Request session
- Rating system
- Availability schedule

**Backend**:
- TutorProfile model
- Session booking system

### Feature 6: Quiz/Flashcard Creator

**Description**: Create and share study flashcards

**Components**:
- Flashcard creation
- Flashcard decks
- Spaced repetition
- Share decks
- Quiz mode

**Backend**:
- Flashcard model
- Deck model
- Progress tracking

### Feature 7: Academic Calendar Integration

**Description**: Sync with university academic calendar

**Components**:
- Exam schedule
- Assignment deadlines
- Class schedule
- Event reminders
- iCal export

**Backend**:
- Event model
- Calendar sync API
- Notification triggers

---

## UI/UX Improvements

### Bottom Navigation (Current)

**Icons (5 tabs)**:
| Tab | Icon | Label |
|-----|------|-------|
| 1 | ⌂ | Home |
| 2 | 📖 | Resources |
| 3 | 📂 | Library |
| 4 | 📑 | Saved |
| 5 | ☰ | More |

**Design Specs**:
- Background: #FFFFFF
- Shadow: elevation 10
- Height: 65-85pt (platform-aware)
- Active color: #22C55E (green)
- Inactive color: #9CA3AF (gray)

### Dashboard Cards

**Design System**:
- Border radius: 16pt
- Shadow: subtle (0 2 8 rgba(0,0,0,0.08))
- Padding: 16pt
- Background: white
- Gap between cards: 16pt

### Resource Cards

**Layout**:
```
┌─────────────────────────────────┐
│ [Thumbnail]  Title               │
│              Course Code         │
│              Type • Rating       │
├─────────────────────────────────┤
│ ❤️  🔖  ⬇️  📤                  │
└─────────────────────────────────┘
```

### Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Primary | #22C55E | Buttons, active states |
| Primary Dark | #16A34A | Pressed states |
| Secondary | #3B82F6 | Links, info |
| Background | #F9FAFB | Screen background |
| Card | #FFFFFF | Card background |
| Text Primary | #111827 | Headings |
| Text Secondary | #6B7280 | Body text |
| Text Tertiary | #9CA3AF | Captions |
| Border | #E5E7EB | Dividers |
| Success | #10B981 | Success states |
| Warning | #F59E0B | Warnings |
| Error | #EF4444 | Errors |

### Typography

| Style | Size | Weight |
|-------|------|--------|
| H1 | 28pt | Bold (700) |
| H2 | 24pt | Bold (700) |
| H3 | 20pt | SemiBold (600) |
| Body | 16pt | Regular (400) |
| Body Small | 14pt | Regular (400) |
| Caption | 12pt | Regular (400) |

---

## Backend API Requirements

### New Endpoints Needed

```python
# Resources
GET    /api/resources/my-uploads/
POST   /api/resources/{id}/share/
POST   /api/resources/{id}/share-to-student/
POST   /api/resources/{id}/share-to-group/
GET    /api/resources/{id}/share-count/

# Collaboration Features
GET    /api/collaboration/study-sessions/
POST   /api/collaboration/study-sessions/
GET    /api/collaboration/flashcards/
POST   /api/collaboration/flashcards/
GET    /api/collaboration/tutors/
POST   /api/collaboration/tutors/request/

# Calendar
GET    /api/calendar/events/
POST   /api/calendar/events/

# User Search
GET    /api/accounts/users/search/
```

### Database Models

```python
# Resource Share Event
class ResourceShareEvent(models.Model):
    resource = ForeignKey('resources.Resource')
    sender = ForeignKey('accounts.User')
    receiver = ForeignKey('accounts.User', null=True)
    group = ForeignKey('social.StudyGroup', null=True)
    share_method = CharField
    created_at = DateTimeField

# Study Session
class StudySession(models.Model):
    user = ForeignKey('accounts.User')
    duration = IntegerField  # minutes
    type = CharField  # focus/break
    completed_at = DateTimeField

# Flashcard
class FlashcardDeck(models.Model):
    owner = ForeignKey('accounts.User')
    title = CharField
    is_public = BooleanField

class Flashcard(models.Model):
    deck = ForeignKey(FlashcardDeck)
    front = TextField
    back = TextField

# Calendar Event
class CalendarEvent(models.Model):
    user = ForeignKey('accounts.User')
    title = CharField
    event_type = CharField  # exam/assignment/class
    date = DateField
    description = TextField
```

---

## Implementation Priority

| Priority | Feature | Effort |
|----------|---------|--------|
| 1 | Recently Uploaded Files | Low |
| 2 | Share Feature Backend | Medium |
| 3 | Share Feature UI | Medium |
| 4 | Resource Requests | Medium |
| 5 | Study Sessions | Low |
| 6 | Flashcards | Medium |
| 7 | Calendar Integration | Medium |
| 8 | Real-time Study Groups | High |
| 9 | Collaborative Notes | High |
| 10 | Peer Tutoring | High |

---

## Conclusion

This specification provides a comprehensive roadmap for enhancing CampusHub with:

1. **Dashboard improvements** - Adding recently uploaded files section
2. **Share functionality** - Complete backend and UI implementation
3. **7 collaboration features** - Ranging from simple to advanced
4. **UI/UX modernization** - Consistent design system across the app

The implementation should follow the priority order to deliver value incrementally.
