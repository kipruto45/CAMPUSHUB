"""Settings package."""

from decouple import config

environment = config("ENVIRONMENT", default="development")

if environment == "production":
    from .production import *  # noqa: F401, F403, I001
elif environment == "testing":
    from .testing import *  # noqa: F401, F403, I001
else:
    from .development import *  # noqa: F401, F403, I001
