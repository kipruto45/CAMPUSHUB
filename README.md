# CampusHub - University Learning Resources Management System

A production-ready Django REST API backend for a modern University Learning Resources App that allows university students to access academic materials such as notes, lecture slides, past papers, books, assignments, tutorials, and other learning resources.

## Features

### Core Features
- **User Authentication**: JWT-based authentication with role-based access control (Student, Moderator, Admin)
- **Resource Management**: Upload, browse, search, and download learning resources
- **Academic Organization**: Organize resources by faculty, department, course, semester, and unit
- **Social Features**: Bookmark resources, comment on resources, rate resources
- **Moderation**: Admin/Moderator workflow for reviewing and approving uploaded resources
- **Analytics**: Dashboard analytics for admins
- **Notifications**: Automated notifications for resource approval/rejection, comments, ratings
- **Search**: Advanced search with filtering and sorting
- **Reporting System**: Report inappropriate content with moderation workflow

### Personal Library (NEW)
- **Private Storage**: Each student has personal storage space
- **Folder Organization**: Create folders with color labels
- **Save Public Resources**: Save public resources to personal library
- **File Management**: Upload, rename, move, duplicate, delete files
- **Favorites**: Mark files and folders as favorites
- **Recent Files**: Track recently accessed files
- **Storage Tracking**: Monitor storage usage

### Modern Features
- **Multi-file Uploads**: Support for multiple files per resource
- **OCR-Ready**: Extracted text storage for future PDF text search
- **AI Summaries**: AI-generated summaries for notes
- **Smart Tags**: Auto-suggested tags for resources
- **Trending Resources**: Based on views, downloads, and bookmarks
- **Recommendations**: Personalized resource recommendations
- **View-only downloads**: Student downloads/files open via system “Open with…” chooser (web falls back to browser); no edit/save flows on device.

## Tech Stack

- **Python**: 3.12+
- **Django**: 4.2+
- **Django REST Framework**: 3.14+
- **PostgreSQL**: Database
- **JWT**: Token-based authentication
- **Celery + Redis**: Background tasks
- **Cloudinary/S3**: File storage
- **drf-spectacular**: API documentation (Swagger/OpenAPI)
- **Docker & Docker Compose**: Containerization

## Project Structure

```
CampusHub/
├── manage.py
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── nginx.conf
├── .env
├── .env.example
├── README.md
│
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   ├── wsgi.py
│   └── celery.py
│
├── apps/
│   ├── core/              # Core utilities, mixins, permissions
│   ├── accounts/          # User authentication and profiles
│   ├── faculties/         # Faculty and department management
│   ├── courses/          # Course and unit management
│   ├── resources/         # Learning resources + Personal Library
│   ├── bookmarks/         # Resource bookmarking
│   ├── comments/          # Resource comments (threaded)
│   ├── ratings/           # Resource ratings
│   ├── downloads/         # Download tracking
│   ├── notifications/     # User notifications
│   ├── search/            # Resource search
│   ├── analytics/         # Admin analytics
│   ├── moderation/        # Content moderation
│   └── reports/           # Content reporting system
│
├── tests/
│   ├── conftest.py
│   ├── authentication/
│   └── resources/
│
├── media/                 # User uploaded files
├── static/               # Static files
└── templates/            # Django templates
```

## Quick Start (Development)

1. Clone the repository:
```bash
git clone <repository-url>
cd CampusHub
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## API Versioning
- All REST endpoints are now under `/api/v1/…`. Legacy `/api/…` URLs remain temporarily but return `Deprecation: true` headers. See `docs/API_VERSIONING.md` for details and migration steps.
- v2 namespace (`/api/v2/…`) exists as a placeholder and currently returns HTTP 501.
- Legacy/v1 responses include `Link: <.../api/v2/>; rel="successor-version"` to guide clients forward.

## PWA & Offline
- The service worker lives at `/static/pwa/sw.js` with app-shell caching, background sync queue for offline POST requests, and API caching tuned for `/api/v1` (download responses also send `X-Download-Directory`).
- Register it from the web client early in app startup, e.g.:
  ```html
  <script src="/static/pwa/register-sw.js" defer></script>
  ```
- Manifest is available at `/static/pwa/manifest.json` with scope `/`; offline fallback page is `/offline/`.

## Email & Notifications
- Set `FRONTEND_BASE_URL` and SMTP settings (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS/SSL`, `DEFAULT_FROM_EMAIL`) to ensure all verification/password/payment emails render clickable links.
- Payment success/refund emails attach PDF receipts and include secure download links; SMS messages include the signed receipt URL.

## Downloads (Mobile)
- Configuration endpoint: `/api/v1/mobile/download-config/` returns `DOWNLOAD_DIRECTORY`, `DOWNLOAD_TO_APP_DIRECTORY`, `PREVENT_SYSTEM_DOWNLOADS`.
- Download responses also return `X-Download-Directory` and `X-Prevent-System-Downloads` headers.

## Trash / Restore
- Resources support soft-delete (`is_deleted/deleted_at`). Admin can restore via the restore action/endpoint; non-admin views should use `Resource.objects` to exclude trashed items.

## Bulk Upload (Admin)
- Admin bulk upload accepts ZIPs, skips oversized/invalid file types, and reports success/warnings. Optional status/public flags are supported via form fields.

5. Run migrations:
```bash
python manage.py migrate
```

6. Create superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

## Mobile App Backend Connection (Expo)

Set the mobile API URL before starting the app:

```bash
export EXPO_PUBLIC_API_URL=http://127.0.0.1:8000/api
```

Host mapping notes:
- Android emulator: `http://10.0.2.2:8000/api`
- iOS simulator: `http://127.0.0.1:8000/api`
- Physical device: `http://<your-lan-ip>:8000/api`

### Mobile screen smoke test (pre-release)

Compile all Expo routes/screens as a release smoke check:

```bash
cd mobile
npm run test:screens
```

## Docker Setup (Recommended for Production)

1. Build and run with Docker Compose:
```bash
docker-compose up --build
```

2. Access the application:
   - Web: http://localhost:8000
   - Swagger UI: http://localhost:8000/api/docs/
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

## Running Background Tasks

Start Celery worker and beat scheduler:
```bash
# Worker
celery -A config worker -l info

# Beat scheduler
celery -A config beat -l info
```

## API Endpoints

### Authentication
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/login/` - Login user
- `POST /api/auth/logout/` - Logout user
- `POST /api/auth/token/refresh/` - Refresh JWT token
- `GET /api/auth/profile/` - Get user profile
- `PATCH /api/auth/profile/` - Update user profile

### Resources
- `GET /api/resources/` - List approved resources
- `POST /api/resources/` - Upload new resource
- `GET /api/resources/{slug}/` - Get resource details
- `PATCH /api/resources/{slug}/` - Update resource
- `DELETE /api/resources/{slug}/` - Delete resource
- `GET /api/resources/my-uploads/` - Get user's uploads
- `GET /api/resources/trending/` - Get trending resources
- `GET /api/resources/recommended/` - Get recommended resources
- `POST /api/resources/{id}/save-personal/` - Save to personal library

### Personal Library
- `GET /api/personal-folders/` - List personal folders
- `POST /api/personal-folders/` - Create folder
- `GET /api/personal-resources/` - List personal files
- `POST /api/personal-resources/` - Upload personal file
- `GET /api/personal-resources/favorites/` - Get favorite files
- `GET /api/personal-resources/recent/` - Get recently accessed
- `GET /api/personal-resources/storage/` - Get storage usage

### Bookmarks
- `GET /api/bookmarks/` - List bookmarks
- `POST /api/bookmarks/` - Create bookmark
- `DELETE /api/bookmarks/{id}/` - Remove bookmark

### Reports
- `POST /api/reports/` - Report content
- `GET /api/reports/` - List reports (admin/moderator)
- `PATCH /api/reports/{id}/` - Update report status
- `POST /api/reports/{id}/resolve/` - Resolve report

### Search
- `GET /api/search/` - Search resources
- `GET /api/search/suggestions/` - Get search suggestions

### Moderation
- `GET /api/moderation/pending-resources/` - List pending resources
- `POST /api/moderation/resources/{id}/approve/` - Approve resource
- `POST /api/moderation/resources/{id}/reject/` - Reject resource

### Analytics
- `GET /api/analytics/dashboard/` - Dashboard statistics
- `GET /api/analytics/resources/` - Most downloaded resources
- `GET /api/analytics/uploaders/` - Most active uploaders

## User Roles

### Student
- Register and login
- View approved resources
- Search and download resources
- Bookmark resources
- Upload resources
- Comment and rate resources
- Edit own profile
- Manage personal library

### Moderator
- All student permissions
- Review uploaded resources
- Approve or reject resources
- Moderate comments
- View and resolve reports

### Admin
- All moderator permissions
- Full access to all data
- Manage users, faculties, departments, courses, units
- View analytics and reports
- Manage moderation workflows

## Environment Variables

See `.env.example` for all available environment variables.

Key variables:
- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to False in production
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `CLOUDINARY_*`: Cloudinary configuration
- `JWT_*`: JWT token settings

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps

# Run specific test file
pytest tests/authentication/
```

## API Documentation

Once the server is running, access the API documentation at:
- Swagger UI: http://localhost:8000/api/docs/
- ReDoc: http://localhost:8000/api/redoc/

## Deployment

### Production Checklist
1. Set `DEBUG=False` in environment
2. Use a strong `SECRET_KEY` (at least 50 chars, high entropy)
3. Configure PostgreSQL database
4. Set up Redis for Celery
5. Configure Cloudinary or S3 for file storage
6. Set up email service
7. Configure CORS allowed origins
8. Set up reverse proxy (Nginx)
9. Configure SSL/HTTPS
10. Run `make prod-readiness PYTHON=venv/bin/python`
11. Run `make prod-verify PYTHON=venv/bin/python` before deployment
12. Bootstrap admin account once:
   - `DJANGO_SUPERUSER_EMAIL=admin@campushub.com DJANGO_SUPERUSER_PASSWORD='StrongPass123!' make ensure-admin PYTHON=venv/bin/python`

### Docker Production
```bash
# Validate compose config
make prod-compose-validate

# Start production stack
docker compose -f docker-compose.prod.yml up -d --build

# Run production backend verification
make prod-verify PYTHON=venv/bin/python

# Run strict production readiness command
make prod-readiness PYTHON=venv/bin/python
```

Notes:
- The production compose stack now populates `/app/static` at container startup and shares it with Nginx through `static_volume`.
- WebSocket traffic is proxied to Daphne on port `8001`; regular HTTP traffic goes to Gunicorn on port `8000`.
- The bundled `nginx.conf` is HTTP-only by default. Terminate TLS at your edge proxy/load balancer and forward `X-Forwarded-Proto: https`.
- If you expose this stack directly without an upstream TLS terminator, set `SECURE_SSL_REDIRECT=False` explicitly and understand that it is not a hardened production deployment.

## License

MIT License
