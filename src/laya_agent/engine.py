"""Shared local utilities and official Laya System-1 workflows."""
import hashlib, json, os, re, shutil, subprocess, time, tomllib
from pathlib import Path
from .client import LayaClient
from .policy import Policy
from .cache import AnswerCache
from .redaction import redact_secrets
from .telemetry import TelemetryLedger

class LayaEngine:
    def __init__(self, client=None, policy=None, cache=None, telemetry=None):
        self.client = client or LayaClient()
        self.policy = policy or Policy.load()
        self.cache = cache or AnswerCache(enabled=self.policy.cache_enabled)
        self.telemetry = telemetry or TelemetryLedger(enabled=self.policy.telemetry_enabled)

    async def decide(self, state, questions):
        t0 = time.perf_counter()
        clean_state = state
        if self.policy.redaction_enabled and isinstance(state, str):
            clean_state, _ = redact_secrets(state)

        # Check answer cache
        cached = self.cache.get(clean_state, questions)
        if cached is not None:
            duration_ms = (time.perf_counter() - t0) * 1000.0
            self.telemetry.record_call(tool="decide", input_tokens_est=len(str(clean_state)) // 4, output_tokens_est=len(str(cached)) // 4, duration_ms=duration_ms, cache_hit=True)
            return cached

        res = await self.client.systemone(clean_state, questions)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        self.telemetry.record_call(tool="decide", input_tokens_est=len(str(clean_state)) // 4, output_tokens_est=len(str(res)) // 4, duration_ms=duration_ms, cache_hit=False)

        if isinstance(res, dict) and not res.get("fallback"):
            self.cache.set(clean_state, questions, res)
        return res

    async def triage_user_goals(self, prompt):
        questions = {
            "is_compound": {"type":"noul", "instructions":"Does this prompt contain more than one distinct subtask or request?"},
            "primary_blocker": {"type":"choice", "instructions":"What is the primary blocker that must be solved first?", "criteria": {
                "packaging_or_build":"Packaging, linking, dylib rpaths, codesigning, or build failure",
                "runtime_exception":"Runtime crash, exception, or invalid runtime behavior",
                "ui_geometry":"Window size, element layout, aspect ratios, CSS/ImGui styling",
                "feature_addition":"New functionality or refactoring request"}}
        }
        data = await self.decide(prompt, questions)
        if data.get("fallback"):
            return {"is_compound_task": None, "recommended_focus": None, "fallback": True, "error": data.get("error")}
        a = data.get("answers", {})
        return {"is_compound_task": a.get("is_compound",{}).get("noul",0) > .5,
                "recommended_focus": a.get("primary_blocker",{}).get("choice"),
                "confidence": a.get("primary_blocker",{}).get("confidence"),
                "directive":"Isolate the primary focus first; defer secondary objectives until the blocker is resolved."}

    async def audit_plan_requirements(self, user_prompt, planned_steps, plan_file_path=""):
        questions = {
            "omits_user_request":{"type":"noul","instructions":"Does the plan miss or overlook any specific requirement in the prompt?"},
            "is_executable":{"type":"noul","instructions":"Are the planned steps clear, concrete, and actionable?"}}
        state = "PROMPT:\n" + user_prompt + "\n\nPLAN:\n" + "\n".join("- "+s for s in planned_steps)
        res = await self.decide(state, questions)
        if res.get("fallback"):
            result = {"status":"indeterminate", "approved":None, "fallback":True, "error":res.get("error")}
        else:
            a = res.get("answers", {})
            omission = a.get("omits_user_request",{}).get("noul",0)
            executable = a.get("is_executable",{}).get("noul",0)
            result = {"status":"reviewed", "approved": omission < .4 and executable >= .6,
                      "omission_risk":omission, "executable_score":executable}
        if plan_file_path:
            path = Path(plan_file_path).expanduser().resolve(); path.parent.mkdir(parents=True, exist_ok=True)
            status = result.get("status", "indeterminate")
            path.write_text("# Implementation Plan\n\n## User Objectives\n"+user_prompt.strip()+"\n\n## Planned Steps\n"+"\n".join(f"- [ ] {s}" for s in planned_steps)+f"\n\n## Plan Audit\n- Status: {status}\n- Approved: {result.get('approved')}\n", encoding="utf-8")
            result["plan_file"] = str(path)
            result["plan_link"] = path.as_uri()
        return result

    async def laya_triage_error(self, error_trace):
        questions = {
            "is_syntax_or_type":{"type":"noul","instructions":"Is this a static type error or syntax error?"},
            "bug_category":{"type":"choice","instructions":"Select the primary cause of this failure:","criteria":{
                "assertion_mismatch":"Test assertion or value expectation failed", "null_undefined":"Null/None/undefined access",
                "missing_dep":"Module, dependency, or file not found", "network_timeout":"Socket, HTTP, or remote connection timeout",
                "auth_forbidden":"Permission denied, expired token, or unauthorized access"}}}
        res = await self.decide(error_trace, questions)
        return {"fallback":True,"error":res.get("error","Laya unavailable")} if res.get("fallback") else res.get("answers",{})

    async def verify_hypothesis(self, hypothesis, evidence):
        res = await self.decide(evidence, {"supported":{"type":"noul","instructions":f"Does the evidence prove or strongly support: '{hypothesis[:1000]}'?"}})
        if res.get("fallback"):
            return {"supported":None,"status":"indeterminate","fallback":True,"error":res.get("error")}
        score = res.get("answers",{}).get("supported",{}).get("noul",0)
        return {"supported":score >= .65,"probability":score,"status":"assessed"}

    async def laya_decide(self, state, questions):
        return await self.decide(state, questions)

    async def filter_candidate_files(self, task="", file_paths=None, candidates=None, paths=None, threshold=.60):
        raw = file_paths or candidates or paths or []
        if not raw: return []
        qs = {"relevant":{"type":"noul","instructions":f"Is this file relevant to completing: '{task[:1000]}'?"}}
        res = await self.client.batch(raw, qs)
        if isinstance(res,dict) and res.get("fallback"): return {"fallback":True,"error":res.get("error"),"candidates":raw}
        kept=[]
        for path,item in zip(raw,res):
            score=item.get("answers",{}).get("relevant",{}).get("noul",0)
            if score >= threshold: kept.append(path)
        if not kept and res:
            ranked=sorted(((p,it.get("answers",{}).get("relevant",{}).get("noul",0)) for p,it in zip(raw,res)),key=lambda x:x[1],reverse=True)
            kept=[p for p,score in ranked if score >= .35]
        return kept if kept else raw

    def fast_symbol_search(self, symbol, path=".", file_glob="", max_results=10, regex=False):
        target=Path(path).expanduser().resolve(); rg=shutil.which("rg")
        if not target.exists(): return {"status":"error","error":f"Path does not exist: {path}"}
        if not rg: return {"status":"unavailable","error":"ripgrep (`rg`) is missing; run scripts/install-deps.sh"}
        cmd=[rg,"--smart-case","--max-count","3","--max-columns","150","--color","never","--line-number","--no-heading"]
        if not regex: cmd.append("-F")
        if file_glob: cmd.extend(["-g",file_glob])
        cmd.extend([symbol,str(target)])
        try:
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=5)
            lines=[line.strip() for line in p.stdout.splitlines() if line.strip()]
            return {"status":"ok" if p.returncode in (0,1) else "error", "matches":lines[:max(1,min(max_results,200))], "truncated":len(lines)>max_results, "stderr":p.stderr[:2000]}
        except subprocess.TimeoutExpired: return {"status":"timeout","query":symbol,"path":path}

    def filter_paths(self, task, paths, threshold=.60):
        base=Path(task or ".").expanduser().resolve()
        # Kept as a local safety filter; semantic relevance is handled by filter_candidate_files.
        excluded={".git","node_modules",".venv","venv","dist","build","__pycache__"}
        result=[]
        for raw in paths:
            p=Path(raw).expanduser(); p=(base/p).resolve() if not p.is_absolute() else p.resolve()
            try: rel=p.relative_to(base)
            except ValueError: continue
            if p.is_file() and not any(x in excluded for x in rel.parts): result.append(str(p))
        return result

    async def distill_command_output(self, goal, raw_output, threshold=.55, spool_dir=None):
        raw_lines = raw_output.splitlines()
        lines = [line.strip() for line in raw_lines if line.strip()]
        if len(lines) <= 12:
            return raw_output

        # Spool raw output to local disk so full evidence is always accessible
        try:
            spool_path = Path(spool_dir or os.getenv("LAYA_SPOOL_DIR", ".laya/spool")).expanduser()
            spool_path.mkdir(parents=True, exist_ok=True)
            content_hash = hashlib.sha256(raw_output.encode("utf-8")).hexdigest()[:16]
            spool_file = spool_path / f"{content_hash}.log"
            if not spool_file.exists():
                spool_file.write_text(raw_output, encoding="utf-8")
            spool_ref = str(spool_file)
        except Exception:
            spool_ref = "spool_unavailable"

        # Chunk lines into semantic blocks (15 lines per chunk) to protect multi-line stack traces
        chunk_size = 15
        chunks = []
        chunk_lines_map = []
        for i in range(0, len(lines), chunk_size):
            block = lines[i:i + chunk_size]
            chunks.append("\n".join(block))
            chunk_lines_map.append(block)

        res = await self.client.batch(chunks, {"relevant": {"type": "noul", "instructions": f"Does this diagnostic/log block contain errors, tracebacks, or evidence for: '{goal[:1000]}'?"}})
        if isinstance(res, dict) and res.get("fallback"):
            return {"fallback": True, "error": res.get("error"), "spool_file": spool_ref, "message": f"Laya distillation unavailable; raw output saved to {spool_ref}. Use local targeted inspection."}

        kept = []
        for block, item in zip(chunk_lines_map, res):
            score = item.get("answers", {}).get("relevant", {}).get("noul", 0)
            if score >= threshold:
                kept.extend(block)

        if not kept:
            return f"--- Distilled Output (0/{len(lines)} lines matched threshold; raw output in {spool_ref}) ---\n" + "\n".join(lines[:6] + ["[...omitted by distillation: no lines passed threshold...]"] + lines[-6:])

        # Deduplicate while preserving line order
        unique_kept = list(dict.fromkeys(kept))
        return f"--- Distilled Output ({len(unique_kept)}/{len(lines)} lines kept; full raw output in {spool_ref}) ---\n" + "\n".join(unique_kept)

    async def locate_code_regions(self, file_path="", task="", path="", goal="", chunk_size=40, threshold=.65):
        name = (file_path or path).strip()
        query = (task or goal).strip()
        if not name or not query:
            return {"status": "error", "error": "file path and task are required"}
        p = Path(name).expanduser().resolve()
        if not p.is_file():
            return {"status": "error", "error": f"File not found: {name}"}
        lines = p.read_text(errors="replace").splitlines()
        if len(lines) <= chunk_size:
            return {"status": "short_file", "line_count": len(lines), "content": "\n".join(f"{i+1}: {v}" for i, v in enumerate(lines))}

        step = max(chunk_size // 2, 10)
        chunks = []
        meta = []
        for start in range(0, len(lines), step):
            end = min(start + chunk_size, len(lines))
            chunks.append("\n".join(lines[start:end]))
            meta.append((start, end))
            if end >= len(lines):
                break

        results = await self.client.batch(chunks, {"target_match": {"type": "noul", "instructions": f"Does this code block contain logic, styling, or config for: '{query[:1000]}'?"}}, timeout=30)
        if isinstance(results, dict) and results.get("fallback"):
            return {"status": "unavailable", "fallback": True, "error": results.get("error"), "file": name}

        ranked = sorted(((it.get("answers", {}).get("target_match", {}).get("noul", 0), i) for i, it in enumerate(results)), reverse=True)
        chosen = [(s, i) for s, i in ranked if s >= threshold]
        if not chosen and ranked and ranked[0][0] >= .40:
            chosen = ranked[:1]

        # Merge contiguous and overlapping ranges to eliminate duplicate token inflation
        sorted_intervals = sorted([(*meta[i], score) for score, i in chosen[:8]], key=lambda x: x[0])
        merged_spans = []
        for start, end, score in sorted_intervals:
            if not merged_spans or start > merged_spans[-1]["end"] + 4:
                merged_spans.append({"start": start, "end": end, "score": score})
            else:
                merged_spans[-1]["end"] = max(merged_spans[-1]["end"], end)
                merged_spans[-1]["score"] = max(merged_spans[-1]["score"], score)

        regions = []
        for span in merged_spans:
            start = span["start"]
            end = span["end"]
            score = span["score"]
            a = max(0, start - 3)
            b = min(len(lines), end + 3)
            regions.append({
                "start_line": start + 1,
                "end_line": end,
                "confidence": score,
                "context_before": "\n".join(f"{j+1}: {lines[j]}" for j in range(a, start)),
                "target": "\n".join(f"{j+1}: {lines[j]}" for j in range(start, end)),
                "context_after": "\n".join(f"{j+1}: {lines[j]}" for j in range(end, b)),
            })
        return {"status": "ok" if regions else "no_match", "file": name, "line_count": len(lines), "regions": regions}

    async def verify_patch_state(self, file_path, expected_snippet, check_syntax=True):
        p = Path(file_path).expanduser().resolve()
        if not p.is_file():
            return {"verified": False, "status": "failed", "error": f"File not found: {file_path}"}
        content = p.read_text(errors="replace")
        if expected_snippet.strip() not in content:
            return {"verified": False, "status": "failed", "error": "Expected snippet not found"}
        syntax = "untested"
        if check_syntax:
            ext = p.suffix.lower()
            try:
                if ext == ".py":
                    # In-memory compile without generating __pycache__ or .pyc side-effect
                    compile(content, str(p), "exec")
                    syntax = "valid_python"
                elif ext == ".json":
                    json.loads(content)
                    syntax = "valid_json"
                elif ext in (".sh", ".bash"):
                    b = shutil.which("bash")
                    if b:
                        cp = subprocess.run([b, "-n", str(p)], capture_output=True, text=True)
                        if cp.returncode:
                            return {"verified": False, "status": "failed", "syntax_error": cp.stderr}
                        syntax = "valid_bash"
                elif ext == ".toml":
                    tomllib.loads(content)
                    syntax = "valid_toml"
                elif ext in (".yaml", ".yml"):
                    try:
                        import yaml
                        yaml.safe_load(content)
                        syntax = "valid_yaml"
                    except ImportError:
                        syntax = "yaml_checker_missing"
            except Exception as exc:
                return {"verified": False, "status": "failed", "syntax_error": str(exc)}
        return {"verified": True, "status": "snippet_present", "syntax": syntax, "note": "Presence and syntax checks do not establish behavioral correctness."}

    async def extract_doc_guidelines(self, doc_path="", focus_topic="", topic="", task="", query="", file_path="", path="", threshold=.55, max_sections=2, max_chars=6000):
        name=(doc_path or file_path or path).strip(); focus=(focus_topic or topic or task or query).strip()
        if not name or not focus: return {"status":"error","error":"document path and focus topic are required"}
        p=Path(name).expanduser().resolve()
        if not p.is_file(): return {"status":"error","error":f"File not found: {name}"}
        content=p.read_text(errors="replace"); sections=[x.strip() for x in re.split(r"\n(?=#{1,3}\s)",content) if x.strip()]
        if len(sections)<=2: return content[:max_chars]
        res=await self.client.batch(sections,{"relevant":{"type":"noul","instructions":f"Does this documentation section provide guidelines for: '{focus[:1000]}'?"}})
        if isinstance(res,dict) and res.get("fallback"): return {"status":"unavailable","fallback":True,"error":res.get("error")}
        scored=sorted(((it.get("answers",{}).get("relevant",{}).get("noul",0),i) for i,it in enumerate(res)),reverse=True)
        selected=[x for x in scored if x[0]>=threshold][:max(1,max_sections)]
        if not selected and scored and scored[0][0]>=.30: selected=scored[:1]
        selected.sort(key=lambda x:x[1]); out=[]
        for score,i in selected:
            if sum(map(len,out))+len(sections[i])>max_chars: break
            out.append(sections[i])
        return {"status":"ok" if out else "no_match","sections":out,"confidence":scored[0][0] if scored else 0}
