"""Analytics REST endpoints for Mission Control and Toolbox."""

from __future__ import annotations

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/analytics", tags=["analytics"])


# Future endpoints will be added here in subsequent tasks
# from fastapi import Depends
# from .auth import verify_token
