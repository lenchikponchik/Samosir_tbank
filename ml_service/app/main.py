"""ML Service — FastAPI prediction microservice.

This is a STUB service. The ML developer should:
1. Replace StubPredictor with real model inference
2. Keep the /predict endpoint and schemas unchanged
3. Add model loading in the lifespan handler
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
import logging

from fastapi import FastAPI

from app.predictor import predictor
from app.schemas import PredictionRequest, PredictionResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load ML models on startup, cleanup on shutdown."""
    logger.info("ML Service starting — using STUB predictor")
    logger.info("TODO: Load CatBoost/LightGBM models here")
    yield
    logger.info("ML Service shutting down")


app = FastAPI(
    title="Заработок ML Service",
    description="Prediction microservice for salary estimation (STUB)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Predict salary quantiles for a given profile vector.

    Returns p25, p50, p75 salary predictions with SHAP values
    and counterfactual improvement suggestions.
    """
    return predictor.predict(request)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "zarabotok-ml", "model": "stub"}
