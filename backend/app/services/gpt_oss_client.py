"""HTTP client for the future gpt-oss-20b salary model."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class GptOssClientError(RuntimeError):
    """Raised when the model service cannot return a payload."""


class GptOssClient:
    """Thin client that sends one prepared payload to the model service."""

    def __init__(self) -> None:
        self.base_url = settings.GPT_OSS_SERVICE_URL.rstrip("/")
        self.analyze_path = settings.GPT_OSS_ANALYZE_PATH
        self.timeout = settings.GPT_OSS_TIMEOUT

    async def generate_once(self, input_payload: dict[str, Any]) -> dict[str, Any]:
        """Call the model once and return raw JSON for backend validation/storage."""
        url = f"{self.base_url}{self.analyze_path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=input_payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("gpt-oss model call failed")
            raise GptOssClientError("gpt-oss model call failed") from exc

        if not isinstance(data, dict):
            raise GptOssClientError("gpt-oss model returned non-object JSON")
        return data


gpt_oss_client = GptOssClient()
