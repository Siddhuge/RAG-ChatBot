"""API-key authentication.

If APP_API_KEYS is set, every protected endpoint requires a matching
`X-API-Key` header. If it's empty (dev), auth is disabled and a warning is
logged at startup.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.api_keys:
        return  # auth disabled
    if not x_api_key or not any(
        hmac.compare_digest(x_api_key, key) for key in settings.api_keys
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
