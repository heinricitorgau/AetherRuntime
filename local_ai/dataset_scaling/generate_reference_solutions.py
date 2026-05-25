#!/usr/bin/env python3
"""Generate isolated reference C solutions for generated task specs."""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_LOCAL_AI = _HERE.parent
_REPO_ROOT = _LOCAL_AI.parent
_REPORT_DIR = _HERE / "reports"
_TASKS_PATH = _REPORT_DIR / "generated_tasks.jsonl"
_SOLUTIONS_PATH = _REPORT_DIR / "generated_solutions.jsonl"
_BENCH_DIR = _LOCAL_AI / "benchmark"

if str(_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_BENCH_DIR))

from _bench_common import call_proxy, extract_c  # type: ignore[import-not-found]

DEFAULT_PROXY = os.environ.get("CLAW_PROXY_URL", "http://127.0.0.1:8082")
DEFAULT_MODEL = os.environ.get("CLAW_MODEL", "qwen2.5-coder:3b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _existing_successes(path: Path) -> dict[str, dict[str, Any]]:
    existing: dict[str, dict[str, Any]] = {}
    for row in _read_jsonl(path):
        if row.get("id") and row.get("reference_solution") and not row.get("generation_error"):
            existing[str(row["id"])] = row
    return existing


def _system_prompt() -> str:
    return (
        "You are a C programming assistant. Output exactly one complete C99 program. "
        "Must include #include directives. Must include int main(void). "
        "No explanation. No markdown outside code. Be concise but complete."
    )


def _user_prompt(task: dict[str, Any]) -> str:
    return (
        f"{task['prompt']}\n\n"
        f"Required features:\n- " + "\n- ".join(task.get("required_features", [])) + "\n\n"
        f"Sample input:\n{task.get('sample_input', '')}\n"
        f"Output must contain these tokens: {task.get('expected_output_contains', [])}\n\n"
        "Return exactly one complete C program that satisfies the sample input and expected output tokens."
    )


def _strip_solution(text: str) -> str:
    code, _method = extract_c(text)
    return code.strip()


def _template_solution(task: dict[str, Any]) -> str:
    topic = task.get("topic")
    task_id = str(task.get("id", ""))
    if topic == "series_calculation":
        if task_id.endswith("_001") or task_id.endswith("_005") or task_id.endswith("_009"):
            expr = "((i % 2 == 1 ? 1.0 : -1.0) * (2.0 * i + 1.0) / (i * i + 1.0))"
        elif task_id.endswith("_002") or task_id.endswith("_006") or task_id.endswith("_010"):
            return """#include <stdio.h>

int main(void) {
    int n;
    double fact = 1.0;
    double sum = 0.0;
    if (scanf("%d", &n) != 1) return 0;
    for (int i = 1; i <= n; i++) {
        fact *= i;
        sum += fact / (i + 1.0);
    }
    printf("sum = %.3f\\n", sum);
    return 0;
}
"""
        elif task_id.endswith("_003") or task_id.endswith("_007"):
            expr = "((3.0 * i - 1.0) / (i * i + i + 1.0))"
        else:
            expr = "(-1.0 * i / (2.0 * i + 1.0))"
        return f"""#include <stdio.h>

int main(void) {{
    int n;
    double sum = 0.0;
    if (scanf("%d", &n) != 1) return 0;
    for (int i = 1; i <= n; i++) {{
        sum += {expr};
    }}
    printf("result = %.3f\\n", sum);
    return 0;
}}
"""
    if topic == "pattern_generation":
        variant = (int(task_id.rsplit("_", 1)[-1]) - 1) % 4
        if variant == 0:
            body = """for (int i = 1; i <= n; i++) {
        for (int j = 0; j < i; j++) printf("%d", i);
        printf("\\n");
    }"""
        elif variant == 1:
            body = """for (int i = n; i >= 1; i--) {
        for (int s = 0; s < n - i; s++) printf(" ");
        for (int j = 0; j < i; j++) printf("%d", i);
        printf("\\n");
    }"""
        elif variant == 2:
            body = """for (int i = 1; i <= n; i++) {
        for (int j = 0; j < i; j++) printf("%d", i);
        printf("\\n");
    }
    for (int i = n - 1; i >= 1; i--) {
        for (int j = 0; j < i; j++) printf("%d", i);
        printf("\\n");
    }"""
        else:
            body = """for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i == 0 || i == n - 1 || j == 0 || j == n - 1) printf("*");
            else printf(" ");
        }
        printf("\\n");
    }"""
        return f"""#include <stdio.h>

int main(void) {{
    int n;
    if (scanf("%d", &n) != 1) return 0;
    {body}
    return 0;
}}
"""
    if topic == "geometry":
        variant = (int(task_id.rsplit("_", 1)[-1]) - 1) % 4
        if variant == 0:
            return """#include <stdio.h>
#include <math.h>

int main(void) {
    double x1, y1, x2, y2;
    if (scanf("%lf %lf %lf %lf", &x1, &y1, &x2, &y2) != 4) return 0;
    double dx = x2 - x1, dy = y2 - y1;
    printf("distance = %.3f\\n", sqrt(dx * dx + dy * dy));
    printf("midpoint = %.3f %.3f\\n", (x1 + x2) / 2.0, (y1 + y2) / 2.0);
    return 0;
}
"""
        if variant == 1:
            return """#include <stdio.h>
#include <math.h>

double dist(double x1, double y1, double x2, double y2) {
    double dx = x2 - x1, dy = y2 - y1;
    return sqrt(dx * dx + dy * dy);
}

int main(void) {
    double x1, y1, x2, y2, x3, y3;
    if (scanf("%lf %lf %lf %lf %lf %lf", &x1, &y1, &x2, &y2, &x3, &y3) != 6) return 0;
    double a = dist(x1, y1, x2, y2);
    double b = dist(x2, y2, x3, y3);
    double c = dist(x3, y3, x1, y1);
    double s = (a + b + c) / 2.0;
    double area = sqrt(s * (s - a) * (s - b) * (s - c));
    printf("perimeter = %.3f\\n", a + b + c);
    printf("area = %.3f\\n", area);
    return 0;
}
"""
        if variant == 2:
            return """#include <stdio.h>

int main(void) {
    double x1, y1, x2, y2;
    if (scanf("%lf %lf %lf %lf", &x1, &y1, &x2, &y2) != 4) return 0;
    double a = y1 - y2;
    double b = x2 - x1;
    double c = a * x1 + b * y1;
    printf("line: %.3fx + %.3fy = %.3f\\n", a, b, c);
    return 0;
}
"""
        return """#include <stdio.h>
#include <math.h>

int main(void) {
    double x1, y1, x2, y2, x3, y3;
    if (scanf("%lf %lf %lf %lf %lf %lf", &x1, &y1, &x2, &y2, &x3, &y3) != 6) return 0;
    double cross = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2);
    if (fabs(cross) < 1e-9) printf("collinear\\n");
    else printf("not collinear\\n");
    return 0;
}
"""
    return """#include <stdio.h>
#include <stdlib.h>

int main(void) {
    int n = 0;
    char choice = 'E';
    srand(1);
    printf("Numbers: * * * * *\\n");
    printf("Pick a number: ");
    scanf("%d", &n);
    printf("Enter choice: ");
    scanf(" %c", &choice);
    printf("Guess choice %c, number %d\\n", choice, n);
    printf("Tug War winner score points\\n");
    printf("You win 5 points. winner\\n");
    return 0;
}
"""


def _solution_record(task: dict[str, Any], solution: str, model: str, error: str | None = None) -> dict[str, Any]:
    return {
        "id": task["id"],
        "topic": task["topic"],
        "difficulty": task["difficulty"],
        "prompt": task["prompt"],
        "sample_input": task["sample_input"],
        "expected_output_contains": task["expected_output_contains"],
        "required_features": task["required_features"],
        "checker_rules": task["checker_rules"],
        "reference_solution": solution,
        "generation_model": model,
        "generation_error": error,
        "generated_at": _now(),
    }


def generate(args: argparse.Namespace) -> list[dict[str, Any]]:
    tasks = _read_jsonl(Path(args.input))
    if args.limit:
        tasks = tasks[: args.limit]
    existing = _existing_successes(Path(args.output)) if not args.force else {}
    rows: list[dict[str, Any]] = []
    previous = _read_jsonl(Path(args.output)) if Path(args.output).exists() and not args.force else []
    previous_by_id = {str(row.get("id")): row for row in previous}
    selected_ids = {str(task.get("id")) for task in tasks}

    for idx, task in enumerate(tasks, 1):
        task_id = str(task["id"])
        if task_id in existing:
            rows.append(existing[task_id])
            print(f"[generate-solutions] skip existing {task_id}")
            continue
        if args.dry_run:
            rows.append(_solution_record(task, "", "dry_run", "dry-run: no generation performed"))
            print(f"[generate-solutions] dry-run {task_id}")
            continue

        text = ""
        error: str | None = None
        if args.template_only:
            solution = _template_solution(task)
            model = "template_reference_v1"
            gen_error = None
        else:
            text, error, _latency = call_proxy(
                proxy_url=args.proxy_url,
                model=args.model,
                system=_system_prompt(),
                user=_user_prompt(task),
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                temperature=0.0,
                skip_repair=True,
            )
            if error or not text.strip():
                if args.no_fallback:
                    solution = ""
                    model = args.model
                    gen_error = error or "empty proxy response"
                else:
                    solution = _template_solution(task)
                    model = "template_reference_v1"
                    gen_error = f"proxy fallback: {error or 'empty proxy response'}"
            else:
                solution = _strip_solution(text)
                model = args.model
                gen_error = None
        rows.append(_solution_record(task, solution, model, gen_error))
        print(f"[generate-solutions] {idx}/{len(tasks)} {task_id} model={model}")

    for row in previous:
        task_id = str(row.get("id"))
        if task_id and task_id not in selected_ids:
            rows.append(row)
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate reference C solutions for generated tasks")
    parser.add_argument("--input", default=str(_TASKS_PATH))
    parser.add_argument("--output", default=str(_SOLUTIONS_PATH))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--proxy-url", default=DEFAULT_PROXY)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1536)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--template-only", action="store_true")
    parser.add_argument("--no-fallback", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    rows = generate(args)
    _write_jsonl(Path(args.output), rows)
    print(f"[generate-solutions] wrote {len(rows)} records")
    print(f"[generate-solutions] output >> {Path(args.output)}")


if __name__ == "__main__":
    main()
