"""Test fixtures / isolation.

Force auth off for the test session regardless of the developer's local .env.
Environment variables take precedence over the .env file in pydantic-settings,
and this module is imported before any test imports app.main (which builds and
caches settings), so the override lands before settings are first read.
"""

import os

os.environ["APP_API_KEYS"] = ""
os.environ["CORS_ORIGINS"] = "*"
# Keep tests offline: never require a real Claude key.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
