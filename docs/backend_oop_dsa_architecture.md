# CampusHub Backend OOP + DSA Architecture

## Service Layer (OOP)

Implemented service classes:

- `RecommendationService` (strategy + factory orchestrator)
- `TrendingRecommender`
- `CourseBasedRecommender`
- `BehaviorBasedRecommender`
- `StorageService`
- `LibraryService`
- `FolderService`
- `NotificationService`
- `DashboardService`
- `SearchService`
- `AnalyticsService`
- `ReportService`
- `CommentTreeService`

## OOP Patterns Applied

- **Abstraction**: `BaseRecommender` defines a shared `recommend(user, limit, exclude_ids)` interface.
- **Polymorphism**: trending/course/behavior recommenders are interchangeable strategies.
- **Encapsulation**: module-specific services own their business logic and hide query details.
- **Strategy Pattern**: recommendation strategies selected at runtime.
- **Factory Pattern**: `RecommendationService.get_recommender()` builds strategy objects.
- **Facade Pattern**: `DashboardService` aggregates multiple service outputs.

## Data Structures Applied

- **Tree (folders)**:
  - Parent/child folder structure via recursive and iterative traversal.
  - Folder move validation prevents cycles.
  - Breadcrumb path generation from parent chain.
- **Tree (comments)**:
  - Comment thread map + nested reply tree.
  - DFS flattening for threaded display rendering.
- **Dictionaries (analytics)**:
  - Downloads by course
  - Views by unit
  - Favorites by resource
  - Active users by faculty
- **Sets (deduplication)**:
  - Remove duplicate resources in hybrid recommendations.
  - Track consumed resource IDs in behavior-based ranking.
  - Prevent duplicate candidate merges.

## Algorithms Implemented

- **Recommendation score algorithm**:
  - Weighted engagement signals: views, downloads, favorites, ratings.
  - Academic profile signals: faculty, department, course, year, semester match.
- **Folder move validation algorithm**:
  - Block self-parenting.
  - Block moves into descendants.
  - Block cross-user moves.
- **Breadcrumb generation algorithm**:
  - Iterative parent traversal to construct root-to-node path.
- **Related resource similarity algorithm**:
  - Same unit + same course + tag overlap + type match.
- **Search relevance algorithm**:
  - Exact and partial title scoring.
  - Tag/course/unit matching.
  - Popularity blending.
- **Analytics ranking algorithms**:
  - Top downloaded/viewed/favorited/rated resources.
  - Most active faculties/users via aggregated counts.

## Suggested Next Enhancements

1. Add dedicated tests for `apps/core/oop_services.py` and `apps/core/algorithms.py`.
2. Expose OOP service outputs through dedicated API endpoints where needed.
3. Introduce caching for expensive analytics/recommendation computations.
4. Add type-checking (`mypy`) for service interfaces.
