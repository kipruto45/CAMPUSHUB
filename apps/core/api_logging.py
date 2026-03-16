"""
API Request/Response Logging and Monitoring for CampusHub.
"""

import json
import logging
import time
import traceback
from datetime import datetime

from django.db import connection
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("api_logger")


class APILogEntry:
    """
    Represents a single API log entry.
    """

    def __init__(self, request, response=None, duration=None, error=None):
        self.request = request
        self.response = response
        self.duration = duration
        self.error = error
        self.timestamp = datetime.now()

    def to_dict(self):
        return {
            "timestamp": self.timestamp.isoformat(),
            "method": self.request.method,
            "path": self.request.path,
            "query_params": dict(getattr(self.request, "query_params", {})),
            "user": (
                str(self.request.user)
                if self.request.user.is_authenticated
                else "anonymous"
            ),
            "user_id": (
                self.request.user.pk if self.request.user.is_authenticated else None
            ),
            "ip_address": self.get_client_ip(),
            "user_agent": self.request.META.get("HTTP_USER_AGENT", ""),
            "response_status": self.response.status_code if self.response else None,
            "duration_ms": self.duration,
            "error": str(self.error) if self.error else None,
        }

    def get_client_ip(self):
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0]
        return self.request.META.get("REMOTE_ADDR")


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware for logging all API requests and responses.
    """

    # Paths to exclude from logging
    EXCLUDE_PATHS = ["/health/", "/ready/", "/metrics/"]

    # Sensitive fields to mask
    SENSITIVE_FIELDS = ["password", "token", "secret", "api_key", "authorization"]

    def process_request(self, request):
        request._request_start_time = time.time()
        request._request_body = request.body

        # Log request
        if not self.should_log(request):
            return

        logger.info(f"Request: {request.method} {request.path}")

    def process_response(self, request, response):
        if not self.should_log(request):
            return response

        duration = None
        if hasattr(request, "_request_start_time"):
            duration = (time.time() - request._request_start_time) * 1000

        # Log response
        APILogEntry(request=request, response=response, duration=duration)

        logger.info(
            f"Response: {request.method} {request.path} - "
            f"Status: {response.status_code} - Duration: {duration:.2f}ms"
        )

        return response

    def process_exception(self, request, exception):
        if not self.should_log(request):
            return

        duration = None
        if hasattr(request, "_request_start_time"):
            duration = (time.time() - request._request_start_time) * 1000

        APILogEntry(request=request, duration=duration, error=exception)

        logger.error(
            f"Error: {request.method} {request.path} - "
            f"{str(exception)} - Duration: {duration:.2f}ms\n{traceback.format_exc()}"
        )

    def should_log(self, request):
        """Check if request should be logged."""
        for path in self.EXCLUDE_PATHS:
            if request.path.startswith(path):
                return False
        return True


class APIAuditLogger:
    """
    Service for auditing API calls.
    """

    @staticmethod
    def log_api_call(
        user, method, path, request_data=None, response_data=None, status_code=None
    ):
        """Log an API call with full details."""
        audit_data = {
            "timestamp": datetime.now().isoformat(),
            "user": str(user) if user else "anonymous",
            "user_id": user.pk if user and user.is_authenticated else None,
            "method": method,
            "path": path,
            "request_data": (
                APIAuditLogger.mask_sensitive_data(request_data)
                if request_data
                else None
            ),
            "response_data": response_data,
            "status_code": status_code,
        }

        logger.info(f"API Audit: {json.dumps(audit_data)}")

    @staticmethod
    def mask_sensitive_data(data):
        """Mask sensitive fields in data."""
        if isinstance(data, dict):
            masked = {}
            for key, value in data.items():
                if any(
                    s in key.lower() for s in ["password", "token", "secret", "api_key"]
                ):
                    masked[key] = "***REDACTED***"
                else:
                    masked[key] = APIAuditLogger.mask_sensitive_data(value)
            return masked
        elif isinstance(data, list):
            return [APIAuditLogger.mask_sensitive_data(item) for item in data]
        return data


class APIMetrics:
    """
    Service for tracking API metrics.
    """

    @staticmethod
    def record_request(method, path, status_code, duration, user_id=None):
        """Record API request metrics."""
        metrics = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
        }
        APICallTracker.track_call(path, method, status_code, float(duration or 0))
        logger.info(f"API Metrics: {json.dumps(metrics)}")

    @staticmethod
    def get_endpoint_stats(path_pattern, time_range_hours=24):
        """
        Get statistics for an endpoint.
        """
        stats = APICallTracker.get_stats(endpoint=path_pattern)
        total_requests = sum(item["total_calls"] for item in stats.values())
        if total_requests == 0:
            avg_duration = 0.0
            error_rate = 0.0
        else:
            weighted_duration = sum(
                item["avg_response_time"] * item["total_calls"]
                for item in stats.values()
            )
            total_errors = sum(item["error_count"] for item in stats.values())
            avg_duration = weighted_duration / total_requests
            error_rate = (total_errors / total_requests) * 100

        return {
            "path_pattern": path_pattern,
            "time_range_hours": time_range_hours,
            "total_requests": total_requests,
            "avg_duration_ms": round(avg_duration, 2),
            "error_rate": round(error_rate, 2),
            "endpoint_breakdown": stats,
        }


class RequestResponseLogger:
    """
    Detailed request/response logging for debugging.
    """

    @staticmethod
    def log_request(request):
        """Log full request details."""
        log_data = {
            "type": "request",
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.path,
            "query_params": dict(getattr(request, "query_params", {})),
            "headers": RequestResponseLogger.get_headers(request.META),
            "body": RequestResponseLogger.get_body(request),
        }

        logger.debug(f"Request Details: {json.dumps(log_data)}")

    @staticmethod
    def log_response(request, response, duration):
        """Log full response details."""
        log_data = {
            "type": "response",
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration_ms": duration,
            "headers": dict(response.items()),
        }

        logger.debug(f"Response Details: {json.dumps(log_data)}")

    @staticmethod
    def get_headers(meta):
        """Extract relevant headers from request."""
        headers = {}
        for key, value in meta.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].replace("_", "-")
                if header_name.lower() not in ["authorization", "cookie"]:
                    headers[header_name] = value
        return headers

    @staticmethod
    def get_body(request):
        """Extract body from request."""
        if hasattr(request, "data"):
            body = request.data
            if isinstance(body, dict):
                return RequestResponseLogger.mask_sensitive(body)
        return None

    @staticmethod
    def mask_sensitive(data):
        """Mask sensitive fields."""
        if isinstance(data, dict):
            return {
                k: (
                    "***"
                    if k.lower() in ["password", "token", "secret", "api_key"]
                    else v
                )
                for k, v in data.items()
            }
        return data


class APIPerformanceMonitor:
    """
    Monitor API performance and track slow requests.
    """

    SLOW_REQUEST_THRESHOLD_MS = 1000  # 1 second

    @staticmethod
    def is_slow_request(duration_ms):
        """Check if request is considered slow."""
        return duration_ms > APIPerformanceMonitor.SLOW_REQUEST_THRESHOLD_MS

    @staticmethod
    def log_slow_request(request, duration_ms, response=None):
        """Log slow requests for investigation."""
        logger.warning(
            f"SLOW REQUEST: {request.method} {request.path} took {duration_ms:.2f}ms"
        )

        # Log query count if available
        if hasattr(connection, "queries") and connection.queries:
            logger.warning(f"Queries: {len(connection.queries)}")
            for query in connection.queries[:10]:  # Log first 10 queries
                logger.warning(f"Query: {query['sql'][:200]}")

    @staticmethod
    def get_db_query_count():
        """Get number of database queries for current request."""
        if hasattr(connection, "queries"):
            return len(connection.queries)
        return 0


class APICallTracker:
    """
    Track API calls for analytics and monitoring.
    """

    # In-memory storage (would use Redis or database in production)
    _call_counts = {}
    _error_counts = {}
    _response_times = {}

    @classmethod
    def track_call(cls, endpoint, method, status_code, duration_ms):
        """Track an API call."""
        key = f"{method}:{endpoint}"

        # Count total calls
        cls._call_counts[key] = cls._call_counts.get(key, 0) + 1

        # Count errors
        if status_code >= 400:
            cls._error_counts[key] = cls._error_counts.get(key, 0) + 1

        # Track response times
        if key not in cls._response_times:
            cls._response_times[key] = []
        cls._response_times[key].append(duration_ms)

        # Keep only last 1000 response times
        if len(cls._response_times[key]) > 1000:
            cls._response_times[key] = cls._response_times[key][-1000:]

    @classmethod
    def get_stats(cls, endpoint=None):
        """Get statistics for API calls."""
        stats = {}

        for key in cls._call_counts:
            if endpoint and endpoint not in key:
                continue

            total = cls._call_counts.get(key, 0)
            errors = cls._error_counts.get(key, 0)
            times = cls._response_times.get(key, [])

            stats[key] = {
                "total_calls": total,
                "error_count": errors,
                "error_rate": (errors / total * 100) if total > 0 else 0,
                "avg_response_time": sum(times) / len(times) if times else 0,
                "min_response_time": min(times) if times else 0,
                "max_response_time": max(times) if times else 0,
            }

        return stats

    @classmethod
    def reset_stats(cls):
        """Reset all statistics."""
        cls._call_counts = {}
        cls._error_counts = {}
        cls._response_times = {}


class EndpointHealthChecker:
    """
    Monitor health of API endpoints.
    """

    @staticmethod
    def check_endpoint_health(endpoint, timeout=5):
        """Check if an endpoint is healthy."""
        stats = APIMetrics.get_endpoint_stats(endpoint)
        avg_response_time = float(stats.get("avg_duration_ms", 0) or 0)
        error_rate = float(stats.get("error_rate", 0) or 0)
        healthy = error_rate < 20 and avg_response_time <= (timeout * 1000)

        return {
            "endpoint": endpoint,
            "healthy": healthy,
            "last_checked": datetime.now().isoformat(),
            "avg_response_time_ms": round(avg_response_time, 2),
            "error_rate": round(error_rate, 2),
            "sample_size": int(stats.get("total_requests", 0) or 0),
        }

    @staticmethod
    def get_all_endpoints_health():
        """Get health status of all monitored endpoints."""
        endpoint_stats = APICallTracker.get_stats()
        if not endpoint_stats:
            return []

        endpoints = sorted(
            {key.split(":", 1)[1] for key in endpoint_stats.keys() if ":" in key}
        )
        return [
            EndpointHealthChecker.check_endpoint_health(endpoint)
            for endpoint in endpoints
        ]


# Logging configuration
API_LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "api_formatter": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "json_formatter": {
            "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
        },
    },
    "handlers": {
        "api_file": {
            "class": "logging.FileHandler",
            "filename": "logs/api_requests.log",
            "formatter": "api_formatter",
        },
        "api_json_file": {
            "class": "logging.FileHandler",
            "filename": "logs/api_json.log",
            "formatter": "json_formatter",
        },
    },
    "loggers": {
        "api_logger": {
            "handlers": ["api_file", "api_json_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
