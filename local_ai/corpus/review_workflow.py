#!/usr/bin/env python3
"""Human review workflow for the corpus (V10).

Actions move an item through the lifecycle, each leaving an append-only history
entry (in the record), an audit-log line, and a per-action Markdown receipt. The
corpus is only ever changed through these actions — never by hand-editing files.

Actions:
  submit   verified/candidate  -> review/in_review    (agent-verifies on submit)
  review   review/in_review     -> review/in_review    (records a reviewer note)
  approve  review/in_review     -> verified/human_verified
  reject   review/in_review     -> archive/rejected
  archive  any                  -> archive/archived
  promote-golden  verified/human_verified -> verified/golden

GUARDRAIL: reviewer identity for approve/reject/promote-golden must be supplied
by a human (--reviewer); the tool never invents one. human_verified/golden are
only granted via an explicit human action recorded in the audit log.

Usage:
  python local_ai/corpus/review_workflow.py submit --id <task_id>
  python local_ai/corpus/review_workflow.py review --id <id> --reviewer "Jane" --note "looks correct"
  python local_ai/corpus/review_workflow.py approve --id <id> --reviewer "Jane"
  python local_ai/corpus/review_workflow.py reject  --id <id> --reviewer "Jane" --note "wrong output"
  python local_ai/corpus/review_workflow.py archive --id <id>
  python local_ai/corpus/review_workflow.py promote-golden --id <id> --reviewer "Jane"
  python local_ai/corpus/review_workflow.py --self-test
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import corpus_lib as cl  # noqa: E402

_RECEIPTS = cl.METADATA_DIR / "receipts"


def _receipt(action: str, item: dict, extra: str = "") -> None:
    _RECEIPTS.mkdir(parents=True, exist_ok=True)
    ts = cl.now().replace(":", "").replace("-", "")
    path = _RECEIPTS / f"{item['task_id']}__{action}__{ts}.md"
    lines = [
        f"# Corpus Action: {action}",
        "",
        f"- task_id: `{item['task_id']}`",
        f"- new review_status: `{item['review_status']}`",
        f"- verification_level: `{item.get('verification_level')}`",
        f"- reviewer: `{item.get('reviewer')}`",
        f"- at: `{cl.now()}`",
    ]
    if extra:
        lines.append(f"- note: {extra}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _require(found, action: str):
    if not found:
        print(f"[review] ERROR: item not found for {action}", file=sys.stderr)
        sys.exit(1)
    return found


def submit(task_id: str) -> dict:
    found = _require(cl.find_item(task_id), "submit")
    stage, _, item = found
    if item.get("verification_level") != "agent_verified" or item.get("review_status") != "candidate":
        print(f"[review] ERROR: only agent_verified candidates can be submitted "
              f"(got level={item.get('verification_level')} status={item.get('review_status')})",
              file=sys.stderr)
        sys.exit(1)
    cl.agent_verify(item)  # re-verify at submission time
    cl.transition(item, "submit", "in_review")
    cl.move_item(task_id, stage, "review")
    cl.save_item(item, "review")
    cl.append_audit({"action": "submit", "task_id": task_id})
    _receipt("submit", item)
    return item


def review(task_id: str, reviewer: str, note: str) -> dict:
    found = _require(cl.find_item(task_id), "review")
    _, _, item = found
    cl.transition(item, "review", item.get("review_status", "in_review"), reviewer=reviewer, note=note)
    cl.save_item(item, "review")
    cl.append_audit({"action": "review", "task_id": task_id, "reviewer": reviewer, "note": note})
    _receipt("review", item, note)
    return item


def approve(task_id: str, reviewer: str) -> dict:
    found = _require(cl.find_item(task_id), "approve")
    stage, _, item = found
    cl.transition(item, "approve", "approved", to_level="human_verified", reviewer=reviewer)
    cl.move_item(task_id, stage, "verified")
    cl.save_item(item, "verified")
    cl.append_audit({"action": "approve", "task_id": task_id, "reviewer": reviewer,
                     "verification_level": "human_verified"})
    _receipt("approve", item)
    return item


def reject(task_id: str, reviewer: str, note: str) -> dict:
    found = _require(cl.find_item(task_id), "reject")
    stage, _, item = found
    cl.transition(item, "reject", "rejected", reviewer=reviewer, note=note)
    cl.move_item(task_id, stage, "archive")
    cl.save_item(item, "archive")
    cl.append_audit({"action": "reject", "task_id": task_id, "reviewer": reviewer, "note": note})
    _receipt("reject", item, note)
    return item


def archive(task_id: str) -> dict:
    found = _require(cl.find_item(task_id), "archive")
    stage, _, item = found
    cl.transition(item, "archive", "archived")
    cl.move_item(task_id, stage, "archive")
    cl.save_item(item, "archive")
    cl.append_audit({"action": "archive", "task_id": task_id})
    _receipt("archive", item)
    return item


def promote_golden(task_id: str, reviewer: str) -> dict:
    found = _require(cl.find_item(task_id), "promote-golden")
    stage, _, item = found
    if item.get("verification_level") != "human_verified":
        print("[review] ERROR: only human_verified items can be promoted to golden", file=sys.stderr)
        sys.exit(1)
    cl.transition(item, "promote-golden", "golden", to_level="golden", reviewer=reviewer)
    cl.save_item(item, "verified")
    cl.append_audit({"action": "promote-golden", "task_id": task_id, "reviewer": reviewer})
    _receipt("promote-golden", item)
    return item


def _self_test() -> bool:
    # Pure transition-logic check; no files touched.
    item = cl.new_record("t", "src", "p")
    cl.transition(item, "agent_verify", "candidate", to_level="agent_verified")
    cl.transition(item, "submit", "in_review")
    cl.transition(item, "approve", "approved", to_level="human_verified", reviewer="Jane")
    ok = (item["verification_level"] == "human_verified" and item["reviewer"] == "Jane"
          and len(item["history"]) == 4 and item["history"][0]["action"] == "import")
    print(f"[review] self-test {'ok' if ok else 'FAIL'}: history_len={len(item['history'])} "
          f"level={item['verification_level']}")
    return ok


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Corpus human review workflow")
    p.add_argument("action", nargs="?",
                   choices=["submit", "review", "approve", "reject", "archive", "promote-golden"])
    p.add_argument("--id", dest="task_id")
    p.add_argument("--reviewer", default="")
    p.add_argument("--note", default="")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    if not args.action or not args.task_id:
        print("[review] ERROR: action and --id required", file=sys.stderr)
        sys.exit(2)
    needs_reviewer = args.action in ("approve", "reject", "promote-golden", "review")
    if needs_reviewer and not args.reviewer:
        print(f"[review] ERROR: --reviewer (a human name) is required for '{args.action}'", file=sys.stderr)
        sys.exit(2)

    if args.action == "submit":
        item = submit(args.task_id)
    elif args.action == "review":
        item = review(args.task_id, args.reviewer, args.note)
    elif args.action == "approve":
        item = approve(args.task_id, args.reviewer)
    elif args.action == "reject":
        item = reject(args.task_id, args.reviewer, args.note)
    elif args.action == "archive":
        item = archive(args.task_id)
    else:
        item = promote_golden(args.task_id, args.reviewer)
    print(f"[review] {args.action} -> {item['task_id']} "
          f"status={item['review_status']} level={item.get('verification_level')}")


if __name__ == "__main__":
    main()
