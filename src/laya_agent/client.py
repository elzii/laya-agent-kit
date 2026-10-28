"""HTTP client for the user's already-running official Laya server."""
import asyncio
import os
from typing import Any, Dict, List, Optional
import httpx

class LayaClientError(RuntimeError):
    pass

class LayaClient:
    def __init__(self, base_url=None, timeout=None, transport=None):
        self.base_url = (base_url or os.getenv("LAYA_BASE", os.getenv("LAYA_BASE_URL", "http://127.0.0.1:8000"))).rstrip("/")
        self.timeout = timeout or float(os.getenv("LAYA_TIMEOUT", os.getenv("LAYA_REQUEST_TIMEOUT", "12")))
        self.batch_chunk_size = max(1, min(64, int(os.getenv("LAYA_BATCH_CHUNK_SIZE", "48"))))
        self.max_state_chars = max(1000, int(os.getenv("LAYA_MAX_STATE_CHARS", "45000")))
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self, timeout=None) -> httpx.AsyncClient:
        t = timeout or self.timeout
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=t,
                transport=self._transport,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def clamp_state(self, state: Any) -> tuple[str, bool]:
        """Clamps state string to max_state_chars and returns (clamped_text, was_truncated)."""
        text = str(state)
        if len(text) <= self.max_state_chars:
            return text, False
        return text[:self.max_state_chars], True

    async def health(self):
        attempts = []
        client = self._get_client(timeout=4)
        for path in ("/openapi.json", "/docs", "/"):
            try:
                response = await client.get(self.base_url + path)
                attempts.append({"path": path, "status_code": response.status_code})
                if response.status_code < 500:
                    return {"reachable": True, "base_url": self.base_url, "probe": path,
                            "status_code": response.status_code,
                            "api_contract": "not verified by reachability probe"}
            except httpx.HTTPError as exc:
                attempts.append({"path": path, "error": str(exc)})
        return {"reachable": False, "base_url": self.base_url, "attempts": attempts}

    async def systemone(self, state, questions, timeout=None):
        clamped, truncated = self.clamp_state(state)
        payload = {"state": clamped, "questions": questions}
        result = await self._post("/v1/systemone", payload, timeout or self.timeout)
        if isinstance(result, dict) and truncated:
            result["truncated"] = True
        return result

    async def batch(self, states, questions, timeout=25):
        if not states:
            return []
        all_results = []
        clamped_tuples = [self.clamp_state(s) for s in states]
        clamped = [c[0] for c in clamped_tuples]
        client = self._get_client(timeout=timeout)
        try:
            for start in range(0, len(clamped), self.batch_chunk_size):
                payload = {"states": clamped[start:start+self.batch_chunk_size], "questions": questions}
                response = await self._post_with_retry(client, self.base_url + "/v1/systemone/batch", payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                    raise LayaClientError(f"Unexpected batch response structure: {data!r}")
                all_results.extend(data["results"])
            if len(all_results) != len(states):
                raise LayaClientError(f"Batch returned {len(all_results)} results for {len(states)} states")
            return all_results
        except (httpx.HTTPError, ValueError, LayaClientError) as exc:
            return {"error": str(exc), "fallback": True}

    async def _post(self, path, payload, timeout):
        client = self._get_client(timeout=timeout)
        try:
            response = await self._post_with_retry(client, self.base_url + path, payload)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise LayaClientError(f"Expected JSON object from {path}")
            return data
        except (httpx.HTTPError, ValueError, LayaClientError) as exc:
            return {"error": str(exc), "fallback": True}

    async def _post_with_retry(self, client: httpx.AsyncClient, url: str, payload: dict, max_retries: int = 2) -> httpx.Response:
        last_exc = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(url, json=payload)
                if response.status_code in (408, 429, 502, 503, 504) and attempt < max_retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
                return response
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < max_retries:
                    await asyncio.sleep(0.1 * (2 ** attempt))
                    continue
                raise
        if last_exc:
            raise last_exc
        return response
