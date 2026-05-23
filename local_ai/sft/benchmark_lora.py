#!/usr/bin/env python3
"""Compare base model vs LoRA adapter on the offline benchmark task set.

Usage:
  python local_ai/sft/benchmark_lora.py \
      --adapter local_ai/sft/artifacts/test_lora \
      --limit 4

Outputs (local_ai/sft/reports/):
  comparison_report.json    -- machine-readable metrics + per-task results
  comparison_report.md      -- human-readable delta table

The evaluation pipeline is the same as run_baseline.py: code is extracted from
the model response, then checked for structure / compile / runtime / semantic /
keywords. Scoring uses the same weights (structure 15 + keyword 15 + compile
40 + runtime 30 = 100 pts, accepted >= 60).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

_HERE        = Path(__file__).resolve().parent        # local_ai/sft/
_REPO_ROOT   = _HERE.parent.parent
_BENCH_DIR   = _HERE.parent / "benchmark"             # local_ai/benchmark/
_PROMPTS_DIR = _BENCH_DIR / "prompts"
_SFT_REPORTS = _HERE / "reports"
_RETRY_DIR   = _HERE.parent / "retry"                 # local_ai/retry/

_DEFAULT_MODEL      = "Qwen/Qwen2.5-Coder-3B-Instruct"
_DEFAULT_MAX_TOKENS = 384
_ACCEPTED_THRESHOLD = 60
_VERBOSE = False

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.shared.config_loader import (
    ConfigError,
    format_config_error,
    load_benchmark_profile,
    load_config,
    load_dataset_profile,
    load_model_profile,
)
from local_ai.experiments.register_run import register_run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(msg: str) -> None:
    if _VERBOSE:
        print(f"[compare] {msg}", flush=True)


def _write_file(content: str | dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    path.write_text(content, encoding="utf-8")


def _timeout_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    timed_out = 0
    for result in results:
        checks = result.get("checks", {})
        if (
            checks.get("proxy", {}).get("timed_out")
            or checks.get("runtime", {}).get("timed_out")
        ):
            timed_out += 1
    return round(timed_out / len(results), 3)


def _register_compare_experiment(
    *,
    comparison: dict,
    out_dir: Path,
    ts: str,
    benchmark_profile_name: str | None,
    model_profile_name: str | None,
    dataset_profile_name: str | None,
) -> None:
    try:
        lora = comparison.get("lora", {})
        lora_rates = lora.get("rates", {})
        registered = register_run(
            {
                "run_id": f"compare_lora_{Path(str(comparison.get('adapter', 'adapter'))).name}_{ts}",
                "run_type": "compare_lora",
                "model_profile": model_profile_name,
                "model": comparison.get("model"),
                "benchmark_profile": benchmark_profile_name,
                "dataset_profile": dataset_profile_name,
                "adapter_path": comparison.get("adapter"),
                "accepted": lora.get("accepted"),
                "cases_run": comparison.get("tasks"),
                "avg_score": lora.get("avg_score"),
                "compile_rate": lora_rates.get("compile_pass_rate"),
                "runtime_rate": lora_rates.get("runtime_pass_rate"),
                "semantic_rate": lora_rates.get("semantic_pass_rate"),
                "keyword_rate": lora_rates.get("keyword_pass_rate"),
                "timeout_rate": _timeout_rate(comparison.get("lora_results", [])),
                "verdict": comparison.get("verdict"),
                "base": comparison.get("base"),
                "lora": comparison.get("lora"),
                "deltas": comparison.get("deltas"),
                "linked_reports": {
                    "comparison_report_json": str(out_dir / "comparison_report.json"),
                    "comparison_report_md": str(out_dir / "comparison_report.md"),
                    "timestamped_json": str(out_dir / f"comparison_{ts}.json"),
                    "timestamped_md": str(out_dir / f"comparison_{ts}.md"),
                },
                "config_profiles": {
                    "benchmark": benchmark_profile_name,
                    "model": model_profile_name,
                    "dataset": dataset_profile_name,
                },
            }
        )
        print(f"[experiments] registered run_id={registered['run_id']}", flush=True)
    except Exception as exc:
        print(f"[experiments] WARNING: could not register compare_lora run: {exc}", file=sys.stderr, flush=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare base vs LoRA adapter on benchmark tasks"
    )
    p.add_argument("--adapter",    required=True,
                   help="Path to LoRA adapter directory")
    p.add_argument("--benchmark",  default=None,
                   help="Benchmark profile name from config/benchmarks.json")
    p.add_argument("--model",      default=None,
                   help="Base model ID (auto-detected from adapter_config.json)")
    p.add_argument("--source",     default="test",
                   choices=["test", "accepted", "all"],
                   help="Task source (default: test)")
    p.add_argument("--limit",      type=int, default=None,
                   help="Max tasks to evaluate (default: all)")
    p.add_argument("--max-tokens", type=int, default=None,
                   help=f"Max new tokens per response (default: from benchmark profile, or {_DEFAULT_MAX_TOKENS})")
    p.add_argument("--out-dir",    default=None,
                   help=f"Output directory (default: {_SFT_REPORTS})")
    p.add_argument("--verbose",    action="store_true",
                   help="Show detailed progress logs")
    p.add_argument("--round",      default=None, metavar="NAME",
                   help="Retry curriculum round (e.g. round_1). "
                        "Records retry_round and focus_categories in comparison output "
                        "and updates round_registry.json after benchmarking.")
    return p.parse_args()


def _load_round_focus(round_name: str) -> list[str]:
    """Return focus categories for *round_name* from retry_curriculum.json."""
    curriculum_path = _RETRY_DIR / "retry_curriculum.json"
    if not curriculum_path.exists():
        return []
    try:
        curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
        return list(curriculum.get(round_name, {}).get("focus", []))
    except Exception:
        return []


def _update_round_registry(round_name: str, updates: dict) -> None:
    """Merge *updates* into the round_registry entry for *round_name*."""
    registry_path = _RETRY_DIR / "round_registry.json"
    if not registry_path.exists():
        return
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        data.setdefault("rounds", {}).setdefault(round_name, {}).update(updates)
        registry_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        print(f"[compare] WARNING: could not update round registry: {exc}", file=sys.stderr)


# ── Model / adapter resolution ────────────────────────────────────────────────

def _adapter_metadata(adapter_dir: Path) -> dict:
    """Infer adapter/job metadata without changing benchmark scoring."""
    adapter_name = adapter_dir.name
    metadata = {
        "adapter_name": adapter_name,
        "training_job": None,
        "anti_regression_samples": False,
    }
    try:
        jobs = load_config("training_jobs")
        adapter_norm = str(adapter_dir).replace("\\", "/").rstrip("/")
        for name, job in jobs.items():
            output_dir = str(job.get("output_dir", "")).replace("\\", "/").rstrip("/")
            if output_dir == adapter_norm or Path(output_dir).name == adapter_name:
                metadata["training_job"] = name
                metadata["anti_regression_samples"] = bool(job.get("anti_regression_samples", False))
                break
    except Exception:
        pass
    return metadata


def _resolve_model(adapter_dir: Path, override: str | None) -> str:
    if override:
        return override
    cfg = adapter_dir / "adapter_config.json"
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding="utf-8")).get(
                "base_model_name_or_path", _DEFAULT_MODEL
            )
        except Exception:
            pass
    return _DEFAULT_MODEL


def _load_system_prompt() -> str:
    for name in ("code_gen_strict_v2.txt", "code_gen_strict.txt", "code_gen_v1.txt"):
        p = _PROMPTS_DIR / name
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return (
        "You are a C programming assistant. "
        "Output exactly one complete C99 program. Do not explain."
    )


# ── Direct inference (replaces proxy call used by run_baseline.py) ────────────

def _generate(
    model,
    tokenizer,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> tuple[str, float]:
    """Generate one response. Returns (text, latency_ms)."""
    import torch

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    prompt_text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    device = next(model.parameters()).device
    inputs = tokenizer(prompt_text, return_tensors="pt").to(device)

    t0 = time.monotonic()
    with torch.no_grad():
        out_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            temperature=1.0,
            pad_token_id=tokenizer.eos_token_id,
        )
    latency_ms = (time.monotonic() - t0) * 1000.0

    new_ids  = out_ids[0][inputs["input_ids"].shape[1]:]
    response = tokenizer.decode(new_ids, skip_special_tokens=True)
    return response, latency_ms


# ── Per-task evaluation (same pipeline as evaluate_case, without proxy) ───────

def _eval_task(
    task: dict,
    response: str,
    latency_ms: float,
    compiler: str | None,
    work_dir: Path,
) -> dict:
    """Run the full benchmark check pipeline on one generated response.

    Returns a result record in the same schema as run_baseline.evaluate_case().
    """
    from _bench_common import (  # type: ignore[import-not-found]
        check_keywords,
        check_output_tokens,
        check_structure,
        compile_code,
        compute_score,
        extract_c,
        is_truncated,
        run_exe,
        semantic_check,
    )

    case_id = task["id"]
    code, method = extract_c(response)

    # ── Truncation + structure ────────────────────────────────────────────────
    trunc  = is_truncated(code)
    struct = check_structure(code)

    # ── Compile ───────────────────────────────────────────────────────────────
    compile_r: dict = {
        "ok": False, "message": "no compiler",
        "errors": [], "warnings": [], "exe": None,
    }
    if compiler and code.strip():
        compile_r = compile_code(code, case_id, work_dir, compiler)

    # ── Runtime ───────────────────────────────────────────────────────────────
    runtime_r: dict = {
        "ok": False, "timed_out": False, "match_ratio": 0.0,
        "found": [], "missing": task.get("expected_tokens", []),
        "output_head": "",
    }
    exe = compile_r.get("exe")
    if exe:
        run_r = run_exe(exe, task.get("sample_input", ""))
        if run_r.get("timed_out"):
            runtime_r["timed_out"] = True
        elif run_r.get("ok"):
            tok = check_output_tokens(
                run_r.get("output", ""), task.get("expected_tokens", [])
            )
            runtime_r.update({
                "ok":          tok.get("match_ratio", 0.0) > 0,
                "match_ratio": tok.get("match_ratio", 0.0),
                "found":       tok.get("found", []),
                "missing":     tok.get("missing", []),
                "output_head": run_r.get("output", "")[:500],
            })

    # ── Semantic ──────────────────────────────────────────────────────────────
    sem_r: dict = {"passed": False, "warnings": [], "errors": [], "risk_score": 0}
    if code.strip():
        sem_r = semantic_check(code)

    # ── Keywords ──────────────────────────────────────────────────────────────
    expected_kw = task.get("expected_keywords", [])
    kw_r: dict = {
        "passed": False, "score": 0.0, "found": [], "missing": expected_kw,
    }
    if code.strip() and expected_kw:
        kw_r = check_keywords(code, expected_kw)
        kw_r["passed"] = kw_r.get("score", 0.0) >= 0.5

    # ── Score (same weights as run_baseline) ──────────────────────────────────
    score_r = compute_score(
        structure_score=struct.get("score", 0.0),
        keyword_score=kw_r.get("score", 0.0),
        compile_ok=compile_r.get("ok", False),
        runtime_ratio=runtime_r.get("match_ratio", 0.0),
    )
    total = score_r["total"]

    return {
        "id":             case_id,
        "latency_ms":     round(latency_ms),
        "extract_method": method,
        "extracted_code": code[:4000],
        "checks": {
            "proxy":      {"passed": True,  "timed_out": False, "note": "direct-inference"},
            "truncation": {"passed": not trunc, "note": "truncated" if trunc else "complete"},
            "structure":  {
                "passed": struct.get("ok", False),
                "score":  struct.get("score", 0.0),
                "issues": struct.get("issues", []),
            },
            "compile":    {
                "passed":   compile_r.get("ok", False),
                "message":  compile_r.get("message", ""),
                "errors":   compile_r.get("errors", []),
                "warnings": compile_r.get("warnings", []),
            },
            "runtime":    {
                "passed":      runtime_r["ok"],
                "timed_out":   runtime_r["timed_out"],
                "match_ratio": runtime_r["match_ratio"],
                "found":       runtime_r["found"],
                "missing":     runtime_r["missing"],
                "output_head": runtime_r["output_head"],
            },
            "semantic":   {
                "passed":     sem_r.get("passed", False),
                "warnings":   sem_r.get("warnings", []),
                "errors":     sem_r.get("errors", []),
                "risk_score": sem_r.get("risk_score", 0),
            },
            "keyword":    {
                "passed":  kw_r["passed"],
                "score":   kw_r["score"],
                "found":   kw_r["found"],
                "missing": kw_r["missing"],
            },
        },
        "score":           total,
        "score_breakdown": score_r.get("breakdown", {}),
        "accepted":        total >= _ACCEPTED_THRESHOLD,
        "task_meta": {
            "topic":      task.get("topic", ""),
            "difficulty": task.get("difficulty", ""),
            "points":     task.get("points", 0),
            "year":       task.get("year", 0),
            "exam":       task.get("exam", ""),
        },
    }


# ── Benchmark pass (one model variant over all tasks) ─────────────────────────

def _run_pass(
    model,
    tokenizer,
    tasks: list[dict],
    system_prompt: str,
    max_tokens: int,
    label: str,
    compiler: str | None,
    work_dir: Path,
) -> list[dict]:
    results: list[dict] = []
    for i, task in enumerate(tasks, 1):
        _log(f"  [{label}] {i}/{len(tasks)}  {task['id']}")
        user_prompt = (
            task["instruction"].strip()
            + "\n\nWrite the full program, not just helper functions."
        )
        response, latency = _generate(
            model, tokenizer, system_prompt, user_prompt, max_tokens
        )
        rec = _eval_task(task, response, latency, compiler, work_dir)
        rec["model_label"] = label
        results.append(rec)

        chk   = rec["checks"]
        flags = (
            f"compile={'ok' if chk['compile']['passed'] else 'no'}"
            f"  runtime={'ok' if chk['runtime']['passed'] else 'no'}"
            f"  semantic={'ok' if chk['semantic']['passed'] else 'no'}"
            f"  score={rec['score']}"
            f"  {'ACCEPTED' if rec['accepted'] else 'rejected'}"
        )
        _log(f"    {flags}")

    return results


# ── Aggregation (reuses scoring.py compute_metrics) ──────────────────────────

def _aggregate(results: list[dict]) -> dict:
    try:
        from scoring import compute_metrics  # type: ignore[import-not-found]
        return compute_metrics(results)
    except Exception:
        pass
    # Fallback: inline aggregation with same logic
    n = len(results)
    if n == 0:
        return {"cases_run": 0, "accepted": 0, "average_score": 0.0, "rates": {}}

    def _rate(key: str) -> float:
        return (
            sum(1 for r in results if r.get("checks", {}).get(key, {}).get("passed"))
            / n
        )

    accepted = sum(1 for r in results if r.get("accepted"))
    return {
        "cases_run":     n,
        "accepted":      accepted,
        "average_score": round(sum(r["score"] for r in results) / n, 2),
        "rates": {
            "compile_pass_rate":   round(_rate("compile"),   3),
            "runtime_pass_rate":   round(_rate("runtime"),   3),
            "semantic_pass_rate":  round(_rate("semantic"),  3),
            "keyword_pass_rate":   round(_rate("keyword"),   3),
            "truncation_pass_rate": round(_rate("truncation"), 3),
            "accepted_rate":       round(accepted / n, 3),
        },
    }


# ── Markdown report ───────────────────────────────────────────────────────────

def _sign(v: float, fmt: str = ".1f") -> str:
    s = format(abs(v), fmt)
    return f"+{s}" if v > 0 else (f"-{s}" if v < 0 else s)


def _pct(v: float) -> str:
    return f"{v:.0%}"


def _build_markdown(
    base_m: dict,
    lora_m: dict,
    base_results: list[dict],
    lora_results: list[dict],
    tasks: list[dict],
    model_id: str,
    adapter_dir: Path,
) -> str:
    n   = base_m.get("cases_run", len(base_results))
    br  = base_m.get("rates", {})
    lr  = lora_m.get("rates", {})
    ba  = base_m.get("accepted", 0)
    la  = lora_m.get("accepted", 0)
    bs  = base_m.get("average_score", 0.0)
    ls  = lora_m.get("average_score", 0.0)

    verdict = (
        "IMPROVEMENT" if la > ba or ls > bs + 1.0 else
        "REGRESSION"  if la < ba or ls < bs - 1.0 else
        "NO CHANGE"
    )

    lines: list[str] = []
    a = lines.append

    a("# LoRA vs Base Model Benchmark Comparison")
    a("")
    a(f"**Model**:     `{model_id}`  ")
    a(f"**Adapter**:   `{adapter_dir}`  ")
    a(f"**Tasks**:     {n}  ")
    a(f"**Generated**: {_now()}")
    a("")
    a(f"## Verdict: {verdict}")
    a("")
    a("## Aggregate Metrics")
    a("")
    a("| Metric | Base | LoRA | Delta |")
    a("|--------|-----:|-----:|------:|")
    a(f"| Accepted | {ba}/{n} | {la}/{n} | {_sign(la - ba, 'd')} |")
    a(f"| Avg Score | {bs:.1f} | {ls:.1f} | {_sign(ls - bs)} |")

    rate_rows = [
        ("Compile",    "compile_pass_rate"),
        ("Runtime",    "runtime_pass_rate"),
        ("Semantic",   "semantic_pass_rate"),
        ("Keyword",    "keyword_pass_rate"),
        ("Truncation", "truncation_pass_rate"),
    ]
    for label, key in rate_rows:
        bv = br.get(key, 0.0)
        lv = lr.get(key, 0.0)
        d  = lv - bv
        ds = f"+{d:.0%}" if d > 0 else f"{d:.0%}"
        a(f"| {label} | {_pct(bv)} | {_pct(lv)} | {ds} |")

    a("")
    a("## Per-task Results")
    a("")
    a("| ID | Topic | Base | LoRA | Δ | Base | LoRA |")
    a("|----|-------|-----:|-----:|--:|:----:|:----:|")

    base_by_id = {r["id"]: r for r in base_results}
    lora_by_id = {r["id"]: r for r in lora_results}

    for task in tasks:
        tid   = task["id"]
        bres  = base_by_id.get(tid, {})
        lres  = lora_by_id.get(tid, {})
        bsc   = bres.get("score", 0)
        lsc   = lres.get("score", 0)
        topic = (task.get("topic") or "")[:38]
        bchk  = "✓" if bres.get("accepted") else "✗"
        lchk  = "✓" if lres.get("accepted") else "✗"
        a(f"| {tid} | {topic} | {bsc} | {lsc} | {_sign(lsc - bsc)} | {bchk} | {lchk} |")

    a("")
    a("## Check Detail Deltas")
    a("")
    for label, key in rate_rows:
        bv = br.get(key, 0.0)
        lv = lr.get(key, 0.0)
        d  = lv - bv
        ds = f"+{d:.0%}" if d > 0 else f"{d:.0%}"
        a(f"**{label}**")
        a(f"  base:  {_pct(bv)}")
        a(f"  lora:  {_pct(lv)}")
        a(f"  delta: {ds}")
        a("")

    a("---")
    a("*Generated by `benchmark_lora.py` — offline, no proxy, direct model inference.*")

    return "\n".join(lines)


# ── Main run ──────────────────────────────────────────────────────────────────

def _run(args: argparse.Namespace) -> None:
    import torch
    from peft import PeftModel  # type: ignore[import-not-found]
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore[import-not-found]

    # Make benchmark packages importable
    if str(_BENCH_DIR) not in sys.path:
        sys.path.insert(0, str(_BENCH_DIR))

    from _bench_common import find_compiler  # type: ignore[import-not-found]
    from benchmark_cases import load_tasks   # type: ignore[import-not-found]

    benchmark_source = args.source
    benchmark_profile_name = args.benchmark
    model_profile_name = None
    dataset_profile_name = None
    if args.benchmark:
        benchmark = load_benchmark_profile(args.benchmark)
        model_profile_name = str(benchmark["model"])
        dataset_profile_name = str(benchmark["dataset"])
        dataset = load_dataset_profile(str(benchmark["dataset"]))
        model = load_model_profile(str(benchmark["model"]))
        prompt_profiles = load_config("benchmark_profiles")
        prompt_profile = prompt_profiles.get(str(benchmark["prompt_profile"]), {})
        benchmark_source = str(dataset["path"])
        if args.model is None:
            args.model = str(model["hf_model"])
        if args.max_tokens is None:  # --max-tokens not explicitly supplied; use profile value
            args.max_tokens = int(prompt_profile.get("max_tokens", model["max_tokens"]))
    if args.max_tokens is None:
        args.max_tokens = _DEFAULT_MAX_TOKENS

    adapter_dir = Path(args.adapter)
    if not adapter_dir.exists():
        _log(f"ERROR: adapter not found: {adapter_dir}")
        sys.exit(1)
    adapter_meta = _adapter_metadata(adapter_dir)

    model_id = _resolve_model(adapter_dir, args.model)
    out_dir  = Path(args.out_dir) if args.out_dir else _SFT_REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)

    system_prompt = _load_system_prompt()
    compiler      = find_compiler()

    _log(f"model      = {model_id}")
    _log(f"adapter    = {adapter_dir}")
    _log(f"compiler   = {compiler or 'NOT FOUND - compile/runtime skipped'}")
    _log(f"max_tokens = {args.max_tokens}")

    # ── Tasks ─────────────────────────────────────────────────────────────────
    tasks = load_tasks(source=benchmark_source)
    if args.limit:
        tasks = tasks[: args.limit]
    _log(f"tasks      = {len(tasks)}")

    # ── Device / dtype ────────────────────────────────────────────────────────
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda":
        props = torch.cuda.get_device_properties(0)
        dtype: torch.dtype = torch.bfloat16 if props.major >= 8 else torch.float16
        _log(f"CUDA: {torch.cuda.get_device_name(0)}  {props.total_memory // (1024**2)} MB")
    else:
        dtype = torch.float32
        _log("WARNING: no CUDA")
    _log(f"dtype = {dtype}")

    load_kw: dict = {"trust_remote_code": True, "torch_dtype": dtype}
    if device == "cuda":
        load_kw["device_map"] = "auto"

    # ── Base model ────────────────────────────────────────────────────────────
    _log("loading base model ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = AutoModelForCausalLM.from_pretrained(model_id, **load_kw)
    base_model.eval()
    if device == "cuda":
        _log(f"base loaded  CUDA: {torch.cuda.memory_allocated() // (1024**2)} MB")

    # ── Base benchmark ────────────────────────────────────────────────────────
    _log("running base benchmark ...")
    with tempfile.TemporaryDirectory(prefix="bench_base_") as tmp:
        base_results = _run_pass(
            base_model, tokenizer, tasks, system_prompt,
            args.max_tokens, "base", compiler, Path(tmp),
        )

    # ── Load adapter (wraps + merges into base_model weights) ─────────────────
    _log("loading adapter ...")
    lora_model = PeftModel.from_pretrained(base_model, str(adapter_dir))
    lora_model = lora_model.merge_and_unload()
    lora_model.eval()
    _log("adapter merged")

    # ── LoRA benchmark ────────────────────────────────────────────────────────
    _log("running lora benchmark ...")
    with tempfile.TemporaryDirectory(prefix="bench_lora_") as tmp:
        lora_results = _run_pass(
            lora_model, tokenizer, tasks, system_prompt,
            args.max_tokens, "lora", compiler, Path(tmp),
        )

    # ── Aggregate + deltas ────────────────────────────────────────────────────
    _log("computing deltas ...")
    base_m = _aggregate(base_results)
    lora_m = _aggregate(lora_results)

    ba  = base_m.get("accepted", 0)
    la  = lora_m.get("accepted", 0)
    bs  = base_m.get("average_score", 0.0)
    ls  = lora_m.get("average_score", 0.0)
    br  = base_m.get("rates", {})
    lr  = lora_m.get("rates", {})
    n   = len(tasks)

    verdict = (
        "improvement" if la > ba or ls > bs + 1.0 else
        "regression"  if la < ba or ls < bs - 1.0 else
        "no_change"
    )

    comparison = {
        "timestamp":  _now(),
        "model":      model_id,
        "adapter":    str(adapter_dir),
        "adapter_name": adapter_meta["adapter_name"],
        "training_job": adapter_meta["training_job"],
        "anti_regression_samples": adapter_meta["anti_regression_samples"],
        "metadata": {
            "adapter": adapter_meta["adapter_name"],
            "adapter_path": str(adapter_dir),
            "training_job": adapter_meta["training_job"],
            "anti_regression_samples": adapter_meta["anti_regression_samples"],
        },
        "tasks":      n,
        "verdict":    verdict,
        "base": {
            "accepted":    ba,
            "avg_score":   round(bs, 2),
            "rates":       br,
        },
        "lora": {
            "accepted":    la,
            "avg_score":   round(ls, 2),
            "rates":       lr,
        },
        "deltas": {
            "accepted":            la - ba,
            "avg_score":           round(ls - bs, 2),
            "compile_pass_rate":   round(lr.get("compile_pass_rate",  0) - br.get("compile_pass_rate",  0), 3),
            "runtime_pass_rate":   round(lr.get("runtime_pass_rate",  0) - br.get("runtime_pass_rate",  0), 3),
            "semantic_pass_rate":  round(lr.get("semantic_pass_rate", 0) - br.get("semantic_pass_rate", 0), 3),
            "keyword_pass_rate":   round(lr.get("keyword_pass_rate",  0) - br.get("keyword_pass_rate",  0), 3),
        },
        "base_results": base_results,
        "lora_results": lora_results,
    }

    # Attach retry-round metadata when --round is given
    round_focus: list[str] = []
    if args.round:
        round_focus = _load_round_focus(args.round)
        comparison["retry_round"]       = args.round
        comparison["focus_categories"]  = round_focus

    # ── Write reports ─────────────────────────────────────────────────────────
    md_text = _build_markdown(
        base_m, lora_m, base_results, lora_results, tasks, model_id, adapter_dir
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _write_file(comparison, out_dir / f"comparison_{ts}.json")
    _write_file(md_text,    out_dir / f"comparison_{ts}.md")
    _write_file(comparison, out_dir / "comparison_report.json")
    _write_file(md_text,    out_dir / "comparison_report.md")
    _register_compare_experiment(
        comparison=comparison,
        out_dir=out_dir,
        ts=ts,
        benchmark_profile_name=benchmark_profile_name,
        model_profile_name=model_profile_name,
        dataset_profile_name=dataset_profile_name,
    )

    # Update round registry when --round is given
    if args.round:
        _update_round_registry(args.round, {
            "benchmarked":     True,
            "benchmarked_at":  _now(),
            "best_score":      round(ls, 2),
            "regression":      verdict,
            "adapter_path":    str(adapter_dir),
        })

    # ── Summary ───────────────────────────────────────────────────────────────
    _log("done")
    if args.round:
        print(f"\n  retry_round = {args.round}  focus={round_focus}", flush=True)
    print(f"\n  verdict     = {verdict}", flush=True)
    print(f"  accepted    base={ba}/{n}  lora={la}/{n}  delta={la-ba:+d}", flush=True)
    print(f"  avg score   base={bs:.1f}  lora={ls:.1f}  delta={ls-bs:+.1f}", flush=True)
    print(f"  compile     base={_pct(br.get('compile_pass_rate',0))}  lora={_pct(lr.get('compile_pass_rate',0))}  delta={_pct(lr.get('compile_pass_rate',0)-br.get('compile_pass_rate',0))}", flush=True)
    print(f"  runtime     base={_pct(br.get('runtime_pass_rate',0))}  lora={_pct(lr.get('runtime_pass_rate',0))}  delta={_pct(lr.get('runtime_pass_rate',0)-br.get('runtime_pass_rate',0))}", flush=True)
    print(f"  semantic    base={_pct(br.get('semantic_pass_rate',0))}  lora={_pct(lr.get('semantic_pass_rate',0))}", flush=True)
    print(f"\n  report  >> {out_dir / 'comparison_report.md'}", flush=True)
    print(f"  report  >> {out_dir / 'comparison_report.json'}", flush=True)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global _VERBOSE
    args: argparse.Namespace | None = None
    try:
        args = _parse_args()
        _VERBOSE = args.verbose

        round_suffix = f" round={args.round}" if args.round else ""
        print(
            f"[compare] adapter={args.adapter} benchmark={args.benchmark or args.source}"
            f"{round_suffix}",
            flush=True,
        )

        _run(args)

    except SystemExit:
        raise
    except ConfigError as exc:
        print(f"\n{format_config_error(exc)}", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as exc:
        tb_str = traceback.format_exc()
        print(f"\n[compare] FAILED: {exc}", file=sys.stderr, flush=True)
        print(tb_str, file=sys.stderr, flush=True)
        try:
            out_dir = (
                Path(args.out_dir) if args and getattr(args, "out_dir", None)
                else _SFT_REPORTS
            )
            _write_file(
                {"timestamp": _now(), "success": False,
                 "error": str(exc), "traceback": tb_str},
                out_dir / "comparison_report.json",
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
