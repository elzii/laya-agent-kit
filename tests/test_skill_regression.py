from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_context_skill_preserves_retrieval_guardrails():
    text = (ROOT / "skills/laya-context/SKILL.md").read_text()
    required = [
        "repository-native discovery",
        "filter_candidate_files",
        "shortlist, not proof",
        "fast_symbol_search",
        "locate_code_regions",
        "50 lines",
        "line anchors",
        "extract_doc_guidelines",
        "fallback",
        "authorization or security boundary",
    ]
    for phrase in required:
        assert phrase.lower() in text.lower(), f"missing context-skill guardrail: {phrase}"


def test_shared_protocol_does_not_overstate_verification():
    text = (ROOT / "skills/laya-system1-gating/SKILL.md").read_text().lower()
    assert "not proof of behavior" in text
    assert "not an exhaustive truth set" in text
    assert "indeterminate" in text
