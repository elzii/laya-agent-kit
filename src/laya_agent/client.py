"""HTTP client for the user's already-running official Laya server."""
import os
import httpx

class LayaClientError(RuntimeError):
    pass

class LayaClient:
    def __init__(self, base_url=None, timeout=None):
        self.base_url = (base_url or os.getenv("LAYA_BASE", os.getenv("LAYA_BASE_URL", "http://127.0.0.1:8000"))).rstrip("/")
        self.timeout = timeout or float(os.getenv("LAYA_TIMEOUT", os.getenv("LAYA_REQUEST_TIMEOUT", "12")))
        self.batch_chunk_size = max(1, min(64, int(os.getenv("LAYA_BATCH_CHUNK_SIZE", "48"))))
        self.max_state_chars = max(1000, int(os.getenv("LAYA_MAX_STATE_CHARS", "45000")))

    async def health(self):
        attempts = []
        async with httpx.AsyncClient(timeout=4) as client:
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
        payload = {"state": str(state)[:self.max_state_chars], "questions": questions}
        return await self._post("/v1/systemone", payload, timeout or self.timeout)

    async def batch(self, states, questions, timeout=25):
        if not states:
            return []
        all_results = []
        clamped = [str(s)[:self.max_state_chars] for s in states]
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                for start in range(0, len(clamped), self.batch_chunk_size):
                    payload = {"states": clamped[start:start+self.batch_chunk_size], "questions": questions}
                    response = await client.post(self.base_url + "/v1/systemone/batch", json=payload)
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
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.base_url + path, json=payload)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, dict):
                    raise LayaClientError(f"Expected JSON object from {path}")
                return data
        except (httpx.HTTPError, ValueError, LayaClientError) as exc:
            return {"error": str(exc), "fallback": True}
