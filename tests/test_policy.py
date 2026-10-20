from laya_agent.engine import LayaEngine

def test_filter_candidate_files_returns_candidates_on_no_input():
    # Empty candidate input should not require a running Laya server.
    import asyncio
    assert asyncio.run(LayaEngine().filter_candidate_files(task="x", file_paths=[])) == []

def test_distill_short_output_does_not_call_laya():
    import asyncio
    text = "one\ntwo\nthree"
    assert asyncio.run(LayaEngine().distill_command_output("test", text)) == text
