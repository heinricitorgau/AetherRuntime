# research-claw-code

## Quick Demo

```bash
python local_ai/cli.py smoke
python local_ai/cli.py system
python local_ai/cli.py adapters
python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded
python local_ai/demo/demo_walkthrough.py
```

Key docs:

- `local_ai/docs/DEMO_WALKTHROUGH.md`
- `local_ai/docs/PORTFOLIO_SUMMARY.md`
- `docs/PROMPT_ARCHITECTURE.md`
- `docs/PROMPT_STATE_SUMMARY.md`
- `local_ai/demo/reports/demo_index.md`
- `local_ai/demo/reports/demo_summary.md`
- `local_ai/system/reports/architecture_map.md`

## Demo Walkthrough

Use the V8 demo platform to present the project without running models:

```bash
python local_ai/demo/build_demo_index.py
python local_ai/demo/generate_demo_summary.py
python local_ai/demo/demo_walkthrough.py
```

The demo flow highlights smoke validation, adapter governance, task-specific
routing, release snapshots, benchmark reports, and the architecture map.

## Current Status

- V1-V8 infrastructure is complete through demo platform and prompt architecture.
- Latest release snapshot: `local_ai_cli_v7`.
- Smoke test status: PASS.
- `retry_geometry_v3_guarded` is retained as `safe_no_change`.
- No default adapter is selected.
- Synthetic LoRA training is frozen; generated datasets remain isolated
  evaluation and stress-test assets.

## Known Limitations

- No adapter is promoted as default.
- Synthetic SFT candidates caused regression despite validated reference
  solutions.
- Routing currently plans adapter selection; it does not execute model
  inference.
- Benchmark execution still requires the local model/proxy path when explicitly
  invoked.

## System Components

- **Benchmark Infrastructure**: config-driven benchmark profiles with compile,
  runtime, semantic, and keyword validation for coding tasks.
- **Adapter Governance**: promotion policy, adapter registries, regression
  analysis, and safe/no-change tracking for LoRA adapters.
- **Model Governance**: model-replacement benchmarking, weighted promotion
  policy across strict and generated benchmarks, and an approved-models registry.
- **Regression Detection**: policy-driven detector that compares benchmark runs
  over time, auto-resolves a reference run, and emits a governed verdict
  (`pass` / `improvement` / `regression` / `manual_review`) that gates promotion.
- **Continuous Benchmark Trend**: read-only aggregator over run history that
  tracks score trends per model and auto-runs the regression detector on the
  latest run pair (`python local_ai/cli.py trend`).
- **Governance Observability**: a single cross-layer status view of what is
  promoted / safe / rejected / awaiting review across adapters, models,
  datasets, regression, reliability, and profiles (`python local_ai/cli.py governance`).
- **Evaluation Reliability**: read-only audit of run history for reproducibility
  stamps and per-task determinism (flaky-task detection)
  (`python local_ai/cli.py reliability`).
- **Prompt/Profile Governance**: validates that prompt profiles reference real,
  non-empty prompt files and flags non-deterministic temperatures; records an
  approved-profiles registry (`python local_ai/cli.py profiles`).
- **Goldens Governance**: validate + promote human-verified golden cases (drop
  candidates in `local_ai/goldens/candidates/`, compile/runtime verified, tiered
  by provenance) into an approved registry (`python local_ai/cli.py goldens`).
- **Routing Governance**: audits the routing policy and plan so routing can only
  select governance-approved adapters (`python local_ai/cli.py route-audit`).
- **Deployment Readiness Gate**: a single ready/blocked verdict aggregating
  smoke, config, profile, routing, regression, reliability, review-backlog, and
  goldens — blocks release while any blocking check fails or has never run
  (`python local_ai/cli.py deploy`).
- **Import Translation**: opt-in zh→en problem translation at the two data
  import surfaces (corpus import and ingest training prep) via a dedicated
  local model, with originals preserved and a JSON+MD audit report
  (`--translate` on `corpus/import_exam.py` and `ingest/prepare_training.py`).
- **Problem RAG Export**: imported problem prompts (English natively or after
  translation) are automatically written as plain `.md` files into
  `local_ai/rag/docs/problems/` with the RAG index rebuilt, so the local model
  can retrieve problem text via `--rag` (disable with `--no-rag-md`).
- **Retry Loop**: failure mining, curated repair targets, golden examples, and
  guarded retry datasets.
- **Dataset Scaling**: isolated generated task assets, validation reports, and
  synthetic benchmark stress tests.
- **Routing Layer**: task-specific adapter routing that defaults to base and
  only considers approved adapter statuses.
- **Release Snapshot System**: milestone snapshots and report indexes for
  reproducible project state.
- **Demo Platform**: portfolio-ready demo index, summary, and walkthrough.
- **Prompt Architecture**: agent prompts and guardrail state summaries for
  stable future automation.

## Model Governance

Model-replacement decisions go through the same governance discipline as adapter
promotion and dataset promotion: benchmark first, then a policy decides — nothing
is hard-coded.

**1. Benchmark** — compare candidate models against the baseline on stable
profiles (a strict exam benchmark and a generated-task benchmark):

```bash
python local_ai/model_eval/compare_models.py \
    --models qwen25_coder_3b qwen25_coder_14b
```

This writes `local_ai/model_eval/reports/model_comparison.json` / `.md`. The
recommendation in that report is produced by the promotion policy, not by
hand-written rules inside `compare_models.py`.

**2. Comparison** — each candidate is measured per benchmark for accepted,
average score, compile, runtime, and semantic deltas versus the baseline, plus a
`model_override_valid` check that the requested model was actually served.

**3. Promotion** — the policy weighs both benchmarks together:

```bash
python local_ai/model_eval/promote_model.py \
    --comparison local_ai/model_eval/reports/model_comparison.json
```

- `promotion_policy.py` holds the tunable policy: `strict_weight` (0.6),
  `generated_weight` (0.4), `require_override_valid`, and the
  `reject < candidate < safe < default` ladder.
- Decisions: `reject`, `candidate`, `safe_no_change`, `promote_default`,
  `manual_review`, and `invalid_model_override`.
- A strict-benchmark regression combined with a material generated-benchmark
  gain is a **conflict** and resolves to `manual_review` — never an automatic
  "stay on baseline".
- If `model_override_valid` is false, the decision is `invalid_model_override`
  and promotion is blocked.

Reports land at `local_ai/model_eval/reports/model_promotion_report.json` / `.md`.

**4. Approved models** — `local_ai/model_eval/models/approved_models.json` records
every evaluated candidate by decision; `default_model` is only set by a clean
`promote_default` and is never demoted as a side effect.

## Automatic Regression Detection

Detect regressions between benchmark runs without re-running models or touching
scoring. The detector reuses `compare_runs.compare()` and applies a tunable
regression policy (thresholds are data, not code), then emits a governed verdict.

```bash
# Compare two explicit runs
python local_ai/cli.py regression --base <prev_run_id> --new <run_id>

# Auto-resolve the previous run of the same model
python local_ai/cli.py regression --new <run_id>

# Model-free verdict self-test (also run by the smoke test)
python local_ai/cli.py regression --self-test
```

- Verdicts: `pass`, `improvement`, `regression`, `manual_review`
  (regression + improvement signals conflict), `no_reference` (nothing to
  compare against).
- A `regression` verdict exits non-zero so promotion gates and CI can block.
- Signals: accepted delta, average-score delta, compile/runtime pass-rate
  deltas, newly-broken tasks, and any single task dropping beyond the policy
  threshold. The canonical, tunable policy lives in
  `local_ai/shared/regression_policy.py` (or pass `--policy <file.json>`).
- Reports: `local_ai/benchmark/reports/regression/regression_report.{json,md}`.

### Regression guard on promotion gates

The same canonical policy is wired into the **adapter** and **model** promotion
executors as a *monotonic safety overlay* — it can only ever **block** a
promotion, never grant one:

- Adapter (`sft/promote_adapter.py`): a `regression` verdict downgrades
  `promote`/`safe_no_change` → `reject`; a conflicting `manual_review` verdict
  downgrades → `ablation_only`.
- Model (`model_eval/promote_model.py`): a `regression` or `manual_review`
  verdict on either benchmark downgrades `promote_default` → `manual_review`,
  and the headline recommendation is recomputed.
- The guard record (`regression_guard`) is attached to every promotion report and
  registry entry for audit. On current data, all decisions are unchanged —
  the guard only adds a safety net and an audit trail.

## Quick Smoke Test

Run the fast infrastructure smoke test before committing:

```bash
python local_ai/system/smoke_test.py
```

The smoke test validates configs, report indexes, adapter registry summaries,
and routing plans without running models, training adapters, calling the proxy,
or requiring CUDA/torch.

## Unified CLI

Use `local_ai/cli.py` as the main developer entry point for common workflows:

```bash
python local_ai/cli.py smoke
python local_ai/cli.py validate-config
python local_ai/cli.py adapters
python local_ai/cli.py routing --benchmark c_exam_2025_strict_seeded
python local_ai/cli.py regression --new <run_id>
python local_ai/cli.py trend
python local_ai/cli.py reliability
python local_ai/cli.py profiles
python local_ai/cli.py goldens
python local_ai/cli.py route-audit
python local_ai/cli.py deploy
python local_ai/cli.py governance
python local_ai/cli.py system
python local_ai/cli.py snapshot --name local_ai_routing_v4
```

Use `--dry-run` on any subcommand to print the underlying script command without
executing it. The CLI does not include training commands; benchmark execution is
available only through the explicit `benchmark` subcommand.

## Prompt Architecture

Agent and automation prompts should use the current governance state:

- `docs/PROMPT_ARCHITECTURE.md`
- `docs/PROMPT_STATE_SUMMARY.md`

These prompts define the project as local-first AI experimentation
infrastructure, not a chatbot product or production inference service. They
record active guardrails, frozen routes, stable adapters, known limitations, and
preferred future directions.

Core guardrails:

- Do not run unbounded synthetic LoRA training.
- Do not automatically promote adapters.
- Do not modify benchmark scoring as incidental work.
- Do not change routing policy without validation and report updates.
- Do not use benchmark failure outputs as training targets.
- Do not merge unvalidated generated datasets into formal SFT data.

This project is a local-first coding LLM evaluation and LoRA experimentation
framework. It focuses on compile/runtime validated benchmarks, failure mining,
retry training, and adapter governance for offline coding models.

## 使用手冊

`research-claw-code` 是 `claw` CLI 的研究與本地化專案，主要有兩條使用路線：
**離線 bundle**（在有網路的機器打包 `claw + Ollama + 模型`，搬到離線環境直接用）
與 **Rust CLI 開發**（在 `rust/` workspace 內開發 `claw` 本體）。

所有使用教學已整理成獨立的使用手冊：**[`docs/USER_MANUAL.md`](./docs/USER_MANUAL.md)**，
內容包含：

- 離線部署：Level 1 Windows air-gap 目標、bundle 準備/複製/啟動、USB workflow、清理
- 日常使用：離線模式行為、多行輸入、硬體與模型推薦、常用環境變數、除錯與 smoke test
- RAG 與題目資料：本地文件庫、題目中翻英匯入、題目 RAG `.md` 檔
- 評測：C Exam Offline Eval Pack、benchmark 實驗流程
- Rust CLI 開發入口與注意事項

## 專案結構

```text
.
├── local_ai/   # 離線 bundle、proxy、啟動與清理腳本
├── rust/       # claw CLI Rust workspace
├── src/        # 早期 Python port / 研究與對照工具
├── tests/      # Python 端測試與加固驗證
└── docs/       # 使用手冊與補充研究文件
```

## 文件導覽

- [`docs/USER_MANUAL.md`](./docs/USER_MANUAL.md)：完整使用手冊（部署、日常使用、題目匯入、評測）
- [`usage.txt`](./usage.txt)：最短版離線使用說明
- [`USAGE.md`](./USAGE.md)：`claw` CLI 與 Rust workspace 用法
- [`local_ai/README.md`](./local_ai/README.md)：離線 bundle 細節、架構與疑難排解
- [`rust/README.md`](./rust/README.md)：Rust workspace、crate 分工與開發入口
