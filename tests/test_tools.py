from pathlib import Path
from laya_agent.verification import verify_file


def test_verify_file_checks_snippet_and_python_syntax(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("def answer():\n    return 42\n", encoding="utf-8")
    result = verify_file(str(target), "return 42")
    assert result["status"] == "verified"
    assert result["syntax"] == "valid_python"


def test_verify_file_fails_when_expected_text_missing(tmp_path: Path):
    target = tmp_path / "sample.py"
    target.write_text("def answer():\n    return 42\n", encoding="utf-8")
    result = verify_file(str(target), "return 7")
    assert result["status"] == "failed"
    assert "expected_snippet_not_found" in result["issues"]
