from laya_agent.policy import finite_score, indeterminate
import json


def test_finite_score_accepts_valid_score():
    assert finite_score({"answers": {"x": {"noul": 0.7}}}, "x") == 0.7


def test_finite_score_rejects_invalid_or_missing_score():
    assert finite_score({"answers": {"x": {"noul": 1.2}}}, "x") is None
    assert finite_score({"answers": {}}, "x") is None
    assert finite_score({"answers": {"x": {"noul": "nan"}}}, "x") is None


def test_indeterminate_is_not_success():
    result = json.loads(indeterminate("test", RuntimeError("offline")))
    assert result["status"] == "indeterminate"
    assert result["fallback_required"] is True
