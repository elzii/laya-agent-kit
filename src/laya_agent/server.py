"""MCP facade; all System-1 calls target the separately managed official Laya server."""
import json
from mcp.server.fastmcp import FastMCP
from .client import LayaClient
from .engine import LayaEngine

mcp = FastMCP("laya-agent-kit")
engine = LayaEngine(LayaClient())

def _json_list(raw, label, item_type):
    try: value=json.loads(raw)
    except json.JSONDecodeError as exc: return None, {"status":"error","error":f"{label} is invalid JSON: {exc}"}
    if not isinstance(value,list) or not all(isinstance(x,item_type) for x in value):
        return None, {"status":"error","error":f"{label} must be a JSON array of {item_type.__name__} values"}
    return value,None

@mcp.tool()
async def laya_status() -> dict:
    """Check whether the external official Laya server is reachable; does not launch or restart it."""
    return await engine.client.health()

@mcp.tool()
async def filter_candidate_files(task: str = "", file_paths: list[str] | None = None, candidates: list[str] | None = None, paths: list[str] | None = None, threshold: float = 0.60) -> dict | list[str]:
    """Semantic relevance gate for paths discovered with fd/rg; preserves original parameter aliases."""
    return await engine.filter_candidate_files(task, file_paths, candidates, paths, threshold)

@mcp.tool()
def fast_symbol_search(symbol: str, path: str = ".", file_glob: str = "", max_results: int = 10, regex: bool = False) -> dict:
    """Search code/assets with ripgrep; literal matching is the default."""
    return engine.fast_symbol_search(symbol, path, file_glob, max_results, regex)

@mcp.tool()
async def distill_command_output(goal: str, raw_output: str, threshold: float = 0.55) -> str | dict:
    """Semantically distill long terminal/test/browser output through Laya System-1."""
    return await engine.distill_command_output(goal, raw_output, threshold)

@mcp.tool()
async def locate_code_regions(file_path: str = "", task: str = "", path: str = "", goal: str = "", chunk_size: int = 40, threshold: float = 0.65) -> dict:
    """Retrieve relevant line chunks and edit anchors without returning an entire long file."""
    return await engine.locate_code_regions(file_path, task, path, goal, chunk_size, threshold)

@mcp.tool()
async def verify_patch_state(file_path: str, expected_snippet: str, check_syntax: bool = True) -> dict:
    """Check expected text and supported syntax after edits; not a behavioral test."""
    return await engine.verify_patch_state(file_path, expected_snippet, check_syntax)

@mcp.tool()
async def triage_user_goals(prompt: str) -> dict:
    """Classify compound requests and suggest the primary blocker."""
    return await engine.triage_user_goals(prompt)

@mcp.tool()
async def laya_triage_error(error_trace: str) -> dict:
    """Classify an error trace using official Laya System-1."""
    return await engine.laya_triage_error(error_trace)

@mcp.tool()
async def verify_hypothesis(hypothesis: str, evidence: str) -> dict:
    """Score whether supplied evidence supports a proposed root-cause hypothesis."""
    return await engine.verify_hypothesis(hypothesis, evidence)

@mcp.tool()
async def extract_doc_guidelines(doc_path: str = "", focus_topic: str = "", topic: str = "", task: str = "", query: str = "", file_path: str = "", path: str = "", threshold: float = 0.55, max_sections: int = 2, max_chars: int = 6000) -> dict | str:
    """Prune documentation/SKILL.md content to sections relevant to a specified topic."""
    return await engine.extract_doc_guidelines(doc_path, focus_topic, topic, task, query, file_path, path, threshold, max_sections, max_chars)

@mcp.tool()
async def audit_plan_requirements(user_prompt: str, planned_steps: list[str], plan_file_path: str = "") -> dict:
    """Audit a plan for omissions/actionability; optional local Markdown plan output."""
    return await engine.audit_plan_requirements(user_prompt, planned_steps, plan_file_path)

@mcp.tool()
async def laya_decide(state: str, questions: dict) -> dict:
    """Call the general official System-1 endpoint with its native state/questions schema."""
    return await engine.laya_decide(state, questions)

@mcp.tool()
async def laya_systemone_batch(states_json: str, questions_json: str) -> dict | list:
    """Batch System-1 inference. Provide states_json (array of strings) and questions_json (object)."""
    states,err=_json_list(states_json,"states_json",str)
    if err: return err
    try: questions=json.loads(questions_json)
    except json.JSONDecodeError as exc: return {"status":"error","error":f"questions_json is invalid JSON: {exc}"}
    if not isinstance(questions,dict): return {"status":"error","error":"questions_json must be a JSON object"}
    return await engine.client.batch(states,questions)

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__": main()
