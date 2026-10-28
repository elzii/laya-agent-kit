import os
import shutil
from pathlib import Path
import pytest
from src.laya_agent.client import LayaClient
from src.laya_agent.engine import LayaEngine
from tests.fake_laya import FakeLayaTransport


@pytest.mark.asyncio
async def test_locate_code_regions_merges_overlapping_spans(tmp_path):
    # Create a 150-line file
    test_file = tmp_path / "long_module.py"
    lines = [f"def function_{i}():\n    return {i}\n" for i in range(75)]
    test_file.write_text("".join(lines))

    # Transport returns positive scores for chunks
    transport = FakeLayaTransport()
    client = LayaClient(base_url="http://fake:8000", transport=transport)
    engine = LayaEngine(client=client)

    try:
        res = await engine.locate_code_regions(file_path=str(test_file), task="find functions", chunk_size=30, threshold=0.1)
        assert res.get("status") == "ok"
        regions = res.get("regions", [])
        assert len(regions) > 0

        # Verify that regions do not overlap each other
        for idx in range(len(regions) - 1):
            assert regions[idx]["end_line"] < regions[idx + 1]["start_line"], "Regions must not overlap!"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_distill_command_output_spool_and_chunking(tmp_path):
    spool_dir = tmp_path / "spool"
    transport = FakeLayaTransport()
    client = LayaClient(base_url="http://fake:8000", transport=transport)
    engine = LayaEngine(client=client)

    raw_output = "\n".join([f"log line {i}: some information" for i in range(50)])
    try:
        res = await engine.distill_command_output(goal="find errors", raw_output=raw_output, threshold=0.1, spool_dir=str(spool_dir))
        assert isinstance(res, str)
        assert "Distilled Output" in res
        assert str(spool_dir) in res

        # Check that spool file was written on disk
        spool_files = list(spool_dir.glob("*.log"))
        assert len(spool_files) == 1
        assert spool_files[0].read_text(encoding="utf-8") == raw_output
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_verify_patch_state_no_pycache_side_effect(tmp_path):
    py_file = tmp_path / "clean_script.py"
    py_file.write_text("def hello():\n    return 'world'\n")

    engine = LayaEngine()
    res = await engine.verify_patch_state(str(py_file), expected_snippet="return 'world'", check_syntax=True)
    assert res.get("verified") is True
    assert res.get("syntax") == "valid_python"

    # CRITICAL: Verify NO __pycache__ directory was created in tmp_path
    pycache = tmp_path / "__pycache__"
    assert not pycache.exists(), "__pycache__ must NOT be created by verify_patch_state!"
    pyc_files = list(tmp_path.glob("*.pyc"))
    assert len(pyc_files) == 0, ".pyc files must NOT be created!"
