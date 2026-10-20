from laya_agent.engine import LayaEngine

def test_fast_symbol_search(tmp_path):
    (tmp_path / "sample.py").write_text("target_symbol = 1\n")
    result = LayaEngine().fast_symbol_search("target_symbol", str(tmp_path))
    if result.get("status") == "unavailable":
        return
    assert result["status"] == "ok"
    assert any("target_symbol" in line for line in result["matches"])


def test_verify_patch_state_checks_snippet(tmp_path):
    import asyncio
    path = tmp_path / "sample.py"
    path.write_text("answer = 42\n")
    result = asyncio.run(LayaEngine().verify_patch_state(str(path), "answer = 42"))
    assert result["verified"] is True
    missing = asyncio.run(LayaEngine().verify_patch_state(str(path), "answer = 43"))
    assert missing["verified"] is False
