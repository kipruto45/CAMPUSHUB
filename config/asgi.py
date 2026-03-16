"""
ASGI config for CampusHub project.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Initialize Django ASGI application
django_asgi_app = get_asgi_application()

from apps.notifications.middleware import JWTAuthMiddleware  # noqa: E402
# Import WebSocket routing
from apps.notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # HTTP requests
        "http": django_asgi_app,
        # WebSocket requests
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
