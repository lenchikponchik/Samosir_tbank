"""Aggregating router for API v1."""

from fastapi import APIRouter

from app.api.v1.estimates import router as estimates_router
from app.api.v1.history import router as history_router
from app.api.v1.recommendations import router as recommendations_router
from app.api.v1.resumes import router as resumes_router

router = APIRouter(prefix="/api/v1")

router.include_router(resumes_router)
router.include_router(estimates_router)
router.include_router(recommendations_router)
router.include_router(history_router)
