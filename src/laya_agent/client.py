"""Reusable HTTP client for the official Laya service; no server lifecycle management."""
from __future__ import annotations

import os
from typing import Any
import httpx

class LayaClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        self.base_url = (base_url or os.getenv("LAYA_BASE_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout = timeout or float(os.getenv("LAYA_REQUEST_TIMEOUT", "15"))

    async def decide(self, state: str, questions: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}/v1/systemone", json={"state": state, "questions": questions})
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Laya /v1/systemone response was not a JSON object")
        return result

    async def batch(self, requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=max(self.timeout, 20.0)) as client:
            response = await client.post(f"{self.base_url}/v1/systemone/batch", json=requests)
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, list) or len(result) != len(requests):
            raise ValueError("Laya batch response shape/count did not match request")
        return result

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=min(self.timeout, 5.0)) as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            try:
                body = response.json()
            except ValueError:
                body = {"body": response.text[:1000]}
        return {"base_url": self.base_url, "health": body}
