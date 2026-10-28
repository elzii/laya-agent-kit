import time
from pathlib import Path
import pytest
from src.laya_agent.cache import AnswerCache
from src.laya_agent.policy import Policy
from src.laya_agent.redaction import redact_secrets
from src.laya_agent.telemetry import TelemetryLedger


def test_answer_cache_roundtrip(tmp_path):
    cache = AnswerCache(cache_dir=str(tmp_path), enabled=True, ttl=10)
    state = "some code state"
    questions = {"q1": {"type": "noul"}}
    response = {"status": "ok", "answers": {"q1": {"noul": 0.85}}}

    assert cache.get(state, questions) is None
    cache.set(state, questions, response)
    cached = cache.get(state, questions)
    assert cached == response

    # Fallback responses should never be cached
    fallback_resp = {"fallback": True, "error": "timeout"}
    cache.set("other state", questions, fallback_resp)
    assert cache.get("other state", questions) is None


def test_answer_cache_expiration(tmp_path):
    cache = AnswerCache(cache_dir=str(tmp_path), enabled=True, ttl=0.1)
    state = "state"
    questions = {"q": 1}
    cache.set(state, questions, {"data": 123})
    assert cache.get(state, questions) == {"data": 123}
    time.sleep(0.15)
    assert cache.get(state, questions) is None


def test_redact_secrets():
    text = (
        "Here is an API key: sk-abcdef1234567890abcdef1234567890\n"
        "Here is AWS key: AKIAIOSFODNN7EXAMPLE\n"
        "Here is GitHub: ghp_123456789012345678901234567890123456\n"
        "Authorization: Bearer mysecrettoken1234567890\n"
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n"
    )
    sanitized, count = redact_secrets(text)
    assert count >= 4
    assert "sk-abcdef" not in sanitized
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "ghp_12345" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "[REDACTED_AWS_KEY]" in sanitized
    assert "[REDACTED_PRIVATE_KEY]" in sanitized


def test_telemetry_ledger_privacy(tmp_path):
    log_file = tmp_path / "telemetry.jsonl"
    ledger = TelemetryLedger(log_path=str(log_file), enabled=True)

    ledger.record_call(tool="decide", input_tokens_est=50, output_tokens_est=10, duration_ms=12.5)
    assert log_file.exists()

    record = log_file.read_text().strip()
    assert "input_tokens_est" in record
    assert "duration_ms" in record
    # Ensure no source code fields exist in schema
    assert "source" not in record
    assert "code" not in record
    assert "prompt" not in record


def test_policy_load(tmp_path):
    toml_file = tmp_path / "policy.toml"
    toml_file.write_text("""
[retrieval]
max_candidate_files = 42
max_regions = 15

[distillation]
max_output_chars = 9999
long_output_line_threshold = 20

[optimizations]
cache_enabled = true
redaction_enabled = false
telemetry_enabled = true
""")
    policy = Policy.load(str(toml_file))
    assert policy.max_candidate_files == 42
    assert policy.max_regions == 15
    assert policy.max_output_chars == 9999
    assert policy.long_output_line_threshold == 20
    assert policy.cache_enabled is True
    assert policy.redaction_enabled is False
    assert policy.telemetry_enabled is True
