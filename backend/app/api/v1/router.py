"""Top-level API router."""

from fastapi import APIRouter

from backend.app.api.v1 import (
    analytics,
    auth,
    health,
    hospitals,
    patients,
    predictions,
    reports,
    training,
    users,
    xai,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(hospitals.router, prefix="/hospitals", tags=["Hospitals"])
api_router.include_router(patients.router, prefix="/patients", tags=["Patients"])
api_router.include_router(predictions.router, prefix="/predictions", tags=["Predictions"])
api_router.include_router(xai.router, prefix="/xai", tags=["Explainability"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(training.router, prefix="/training", tags=["Training Monitor"])
