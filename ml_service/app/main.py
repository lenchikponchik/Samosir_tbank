"""GPT-OSS-compatible model microservice."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI

from app.predictor import predictor
from app.schemas import PredictionRequest, PredictionResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Load model resources on startup and clean them up on shutdown."""
    logger.info("ML Service starting with GPT-OSS-compatible STUB predictor")
    logger.info("TODO: Load the real gpt-oss-20b runner here")
    yield
    logger.info("ML Service shutting down")


app = FastAPI(
    title="Zarabotok GPT-OSS Model Service",
    description="GPT-OSS-compatible salary analysis microservice (STUB)",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest) -> PredictionResponse:
    """Legacy prediction endpoint kept for old local scripts."""
    return predictor.predict(request)


@app.post("/analyze")
async def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    """Temporary GPT-OSS-compatible endpoint used by backend as the single model call."""
    return predictor.analyze(payload)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "zarabotok-ml", "model": "stub"}
