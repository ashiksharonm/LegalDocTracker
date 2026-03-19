"""
Local development settings for LegalDocTracker.

Extends base.py with debug-friendly overrides.
"""
from .base import *  # noqa: F401, F403

# ---------------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------------

DEBUG = True

ALLOWED_HOSTS = ["*"]

# ---------------------------------------------------------------------------
# Developer conveniences
# ---------------------------------------------------------------------------

INSTALLED_APPS += ["django.contrib.staticfiles"]  # noqa: F405

# Allow the DRF browsable API renderer in local dev
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # noqa: F405
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

# ---------------------------------------------------------------------------
# Database — local defaults (overridden by .env)
# ---------------------------------------------------------------------------

DATABASES["default"].update(  # noqa: F405
    {
        "HOST": "localhost",
        "PORT": "5432",
    }
)

# ---------------------------------------------------------------------------
# CORS — open for local dev
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True
