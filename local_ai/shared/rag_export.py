"""Export imported problem prompts as .md files into the RAG document library.

After a problem enters the system at an import surface (corpus import or
ingest training prep) — already in English, either natively or via the
--translate zh->en step — its final English prompt is written as a plain .md
file under local_ai/rag/docs/problems/ so the local model can retrieve it with
--rag. Files contain ONLY the problem text (no metadata blocks), are keyed by
problem id (idempotent overwrite), and the RAG index is rebuilt after export.

Usage:
  python local_ai/shared/rag_export.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from local_ai.rag.build_index import build_index  # noqa: E402

DEFAULT_PROBLEMS_DIR = _REPO_ROOT / "local_ai" / "rag" / "docs" / "problems"

_UNSAFE_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(problem_id: str) -> str:
    cleaned = _UNSAFE_ID_RE.sub("_", (problem_id or "").strip()).strip("._")
    return f"{cleaned or 'problem'}.md"


def export_problem_md(
    problem_id: str,
    text: str,
    docs_dir: Path | None = None,
) -> Path:
    """Write one problem prompt as a plain .md file; returns the written path."""
    docs_dir = docs_dir or DEFAULT_PROBLEMS_DIR
    docs_dir.mkdir(parents=True, exist_ok=True)
    path = docs_dir / safe_filename(problem_id)
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path


def export_problems(
    problems: list[tuple[str, str]],
    docs_dir: Path | None = None,
    rebuild_index: bool = True,
) -> list[Path]:
    """Export (id, prompt) pairs and rebuild the RAG index once at the end.

    Skips entries with empty prompts. Set rebuild_index=False in tests to keep
    the real index untouched.
    """
    written = [
        export_problem_md(pid, text, docs_dir=docs_dir)
        for pid, text in problems
        if (text or "").strip()
    ]
    if written and rebuild_index:
        build_index()
    return written


# ── Self-test (isolated docs dir, no index rebuild) ──────────────────────────

def _self_test() -> bool:
    import tempfile

    ok = True

    def check(name: str, cond: bool) -> None:
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {name}")
        ok = ok and cond

    check("sanitizes unsafe ids", safe_filename("a b/c:d?") == "a_b_c_d.md")
    check("handles empty id", safe_filename("") == "problem.md")

    with tempfile.TemporaryDirectory() as tmp:
        docs = Path(tmp) / "docs"
        written = export_problems(
            [("t1", "Write a C program."), ("t2", ""), ("t3", "Second problem.")],
            docs_dir=docs,
            rebuild_index=False,
        )
        check("writes only non-empty prompts", len(written) == 2)
        check("content is pure problem text",
              (docs / "t1.md").read_text(encoding="utf-8") == "Write a C program.\n")
        rewritten = export_problem_md("t1", "Updated text.", docs_dir=docs)
        check("overwrite is idempotent by id",
              rewritten.read_text(encoding="utf-8") == "Updated text.\n")

    print(f"[rag-export] self-test {'ok' if ok else 'FAIL'}")
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Export problem prompts to RAG docs")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        sys.exit(0 if _self_test() else 1)
    parser.error("only --self-test is supported; exports run from the import surfaces")


if __name__ == "__main__":
    main()
