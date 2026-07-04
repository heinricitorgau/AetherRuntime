# CORPUS.md — Human-Verified Corpus Platform (V10)

The corpus platform is the project's shift from **synthetic** dataset growth to a
**verified, traceable, human-reviewable** dataset. It lives at `local_ai/corpus/`
and reuses existing verification (benchmark compile/runtime/semantic) — it adds
**no new governance framework, promotion policy, report generator, or benchmark
framework**.

> Goal: every future model improvement should rest on high-quality, traceable,
> human-verifiable real data — not on synthetic claims.

---

## Directory layout

```
local_ai/corpus/
  raw/        imported, uncurated items (pre-corpus; needs human curation)
  verified/   the corpus: candidate / human_verified / golden (by verification_level)
  review/     items currently in human review (EXCLUDED from training)
  archive/    rejected or archived terminal items
  metadata/   corpus_index.json, audit_log.jsonl, receipts/
  reports/    corpus_validation.{json,md}, corpus_dashboard.{json,md}
```

## Record schema

Each corpus item carries:
`task_id, source, topic, difficulty, prompt, reference_solution,
compile_verified, runtime_verified, semantic_verified, review_status, reviewer,
review_timestamp, verification_level` — plus an append-only `history`.

## Verification levels

| Level | Meaning |
|-------|---------|
| `agent_verified` | reference_solution passed automated compile/runtime/semantic checks. Candidate corpus; LoRA-usable. |
| `human_verified` | a human reviewer approved it (recorded `reviewer` + timestamp + audit). |
| `golden` | a human-verified item further locked as a gold reference. |

The agent **never** writes `human_verified` or `golden` — those require a real
`--reviewer` and are recorded in the audit log.

---

## Corpus lifecycle

```
import_exam.py            seed_corpus.py / agent_verify
   raw/  ───────────────►  verified/ (candidate, agent_verified)
                                │  submit
                                ▼
                            review/ (in_review)
                    approve │            │ reject / archive
                            ▼            ▼
              verified/ (human_verified)   archive/ (rejected/archived)
                            │ promote-golden
                            ▼
                    verified/ (golden)
```

Promotion is **append-only** — every transition is recorded in the record's
`history` and in `metadata/audit_log.jsonl`. Nothing is overwritten.

## Review process (`review_workflow.py`)

| Action | From → To | Who |
|--------|-----------|-----|
| `submit` | candidate → in_review | agent (re-verifies on submit) |
| `review` | in_review → in_review (+note) | human (`--reviewer`) |
| `approve` | in_review → human_verified | human (`--reviewer`) |
| `reject` | in_review → rejected (archive) | human (`--reviewer`) |
| `archive` | any → archived | agent/human |
| `promote-golden` | human_verified → golden | human (`--reviewer`) |

Each action writes: the updated record, an audit-log line, and a Markdown receipt
under `metadata/receipts/`. The corpus is changed **only** through these actions.

## Importing real exams (`import_exam.py`)

Supports `.json`, `.pdf`, `.md`, `.txt`. PDF/TXT/MD imports land in `raw/` with
`needs_manual_curation=true`. **Raw OCR/PDF text is never used as finished corpus**
— a human curates the prompt and authors/verifies the reference solution before it
can be agent-verified and submitted for review.

## Promotion rules

- `candidate → human_verified` requires a human `approve` with a reviewer name.
- `human_verified → golden` requires a prior `approve` in history (enforced by
  `validate_corpus.py`).
- Rejected/archived items are terminal and live in `archive/`.

---

## Integration (reuse, not modification)

These integration points are provided as functions in `corpus_lib.py`; they do
**not** modify benchmark scoring, model/adapter governance, routing policy, or the
deploy gate.

- **Benchmark** — `corpus_for_benchmark()` returns verified items in preference
  order **human_verified > golden > agent_verified** (never the reverse).
- **Training (LoRA)** — `candidate_corpus_for_training()` returns only
  `agent_verified` candidates; items in `review/` are **excluded**.
- **Routing (future)** — items carry `topic`, `difficulty`, and
  `verification_level`, the keys a future router can use to choose
  base / adapter / future-model.

## Verification commands

```bash
python local_ai/corpus/build_index.py        # rebuild metadata/corpus_index.*
python local_ai/corpus/validate_corpus.py    # integrity check -> reports/
python local_ai/corpus/corpus_dashboard.py   # quality stats -> reports/
python local_ai/cli.py corpus                # runs all three
```

## Guardrails

- No new governance framework / promotion policy / report generator / benchmark
  framework was added — the platform reuses existing verification.
- Benchmark scoring, model governance, adapter governance, routing policy, and the
  deploy gate are unchanged.
- `human_verified` / `golden` require a real human reviewer; the agent never
  fabricates verification.
