import pytest
from src.laya_agent.client import LayaClient
from tests.fake_laya import FakeLayaTransport


@pytest.mark.asyncio
async def test_fake_laya_systemone_success():
    transport = FakeLayaTransport()
    client = LayaClient(base_url="http://fake-laya:8000", transport=transport)
    try:
        res = await client.systemone("test state", {"test_q": {"type": "noul", "instructions": "test"}})
        assert res.get("status") == "ok"
        assert "test_q" in res.get("answers", {})
        assert "noul" in res["answers"]["test_q"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_fake_laya_batch_success():
    transport = FakeLayaTransport()
    client = LayaClient(base_url="http://fake-laya:8000", transport=transport)
    try:
        states = ["state 1", "state 2", "state 3"]
        res = await client.batch(states, {"test_q": {"type": "noul", "instructions": "test"}})
        assert isinstance(res, list)
        assert len(res) == 3
        for item in res:
            assert "test_q" in item.get("answers", {})
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_fake_laya_timeout_fallback():
    transport = FakeLayaTransport(fault_mode="timeout")
    client = LayaClient(base_url="http://fake-laya:8000", transport=transport)
    try:
        res = await client.systemone("test state", {"test_q": {"type": "noul"}})
        assert res.get("fallback") is True
        assert "error" in res
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_fake_laya_rate_limit_retry():
    transport = FakeLayaTransport(fault_mode="rate_limit")
    client = LayaClient(base_url="http://fake-laya:8000", transport=transport)
    try:
        res = await client.systemone("test state", {"test_q": {"type": "noul"}})
        assert res.get("fallback") is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_fake_laya_truncation_detection():
    transport = FakeLayaTransport()
    client = LayaClient(base_url="http://fake-laya:8000", transport=transport)
    client.max_state_chars = 20
    try:
        long_state = "A" * 100
        res = await client.systemone(long_state, {"test_q": {"type": "noul"}})
        assert res.get("truncated") is True
        # Check that the transport actually received truncated state
        assert len(transport.call_history[-1]["body"]["state"]) == 20
    finally:
        await client.close()
