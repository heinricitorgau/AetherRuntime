#!/usr/bin/env python3
"""One-shot script: inject manually-crafted correct C solutions into round_geometry_v1/retry_dataset.jsonl."""
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
path  = _HERE / "rounds" / "round_geometry_v1" / "retry_dataset.jsonl"

# ── Correct solution for 2025_midterm_003 (Triangle Enumeration) ──────────────
FIX_003 = r"""#include <stdio.h>
#include <math.h>

double dist(double x1, double y1, double x2, double y2) {
    double dx = x2 - x1, dy = y2 - y1;
    return sqrt(dx * dx + dy * dy);
}

double heron_area(double a, double b, double c) {
    double s = (a + b + c) / 2.0;
    return sqrt(s * (s - a) * (s - b) * (s - c));
}

int is_collinear(double x1, double y1, double x2, double y2, double x3, double y3) {
    return fabs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) < 1e-9;
}

int main(void) {
    double x[4], y[4];
    for (int i = 0; i < 4; i++) scanf("%lf %lf", &x[i], &y[i]);
    for (int i = 0; i < 4; i++) {
        for (int j = i + 1; j < 4; j++) {
            for (int k = j + 1; k < 4; k++) {
                if (is_collinear(x[i], y[i], x[j], y[j], x[k], y[k])) {
                    printf("collinear\n");
                } else {
                    double a = dist(x[i], y[i], x[j], y[j]);
                    double b = dist(x[j], y[j], x[k], y[k]);
                    double c = dist(x[k], y[k], x[i], y[i]);
                    printf("area %.3f\n", heron_area(a, b, c));
                }
            }
        }
    }
    return 0;
}"""

# ── Correct solution for 2022_exam2_002 / 2023_exam2_002 (Geometry Toolkit) ──
FIX_TOOLKIT = r"""#include <stdio.h>
#include <math.h>

double point_dist(double x1, double y1, double x2, double y2) {
    return sqrt((x2-x1)*(x2-x1) + (y2-y1)*(y2-y1));
}

double triangle_area(double x1, double y1, double x2, double y2, double x3, double y3) {
    double a = point_dist(x1, y1, x2, y2);
    double b = point_dist(x2, y2, x3, y3);
    double c = point_dist(x3, y3, x1, y1);
    double s = (a + b + c) / 2.0;
    return sqrt(s * (s-a) * (s-b) * (s-c));
}

double point_to_line(double px, double py, double A, double B, double C) {
    return fabs(A*px + B*py + C) / sqrt(A*A + B*B);
}

void print_line(double x1, double y1, double x2, double y2) {
    double A = y2 - y1;
    double B = x1 - x2;
    double C = A*x1 + B*y1;
    printf("%.4fx + %.4fy = %.4f\n", A, B, C);
}

int main(void) {
    double x1, y1, x2, y2, x3, y3;
    double la, lb, lc;
    scanf("%lf %lf %lf %lf %lf %lf", &x1, &y1, &x2, &y2, &x3, &y3);
    scanf("%lf %lf %lf", &la, &lb, &lc);
    printf("Area: %.4f\n", triangle_area(x1, y1, x2, y2, x3, y3));
    printf("D1: %.4f\n", point_to_line(x1, y1, la, lb, -lc));
    printf("D2: %.4f\n", point_to_line(x2, y2, la, lb, -lc));
    printf("D3: %.4f\n", point_to_line(x3, y3, la, lb, -lc));
    print_line(x1, y1, x2, y2);
    print_line(x2, y2, x3, y3);
    print_line(x3, y3, x1, y1);
    return 0;
}"""


def main() -> None:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in records:
        tid = r.get("meta", {}).get("task_id", "")
        if tid == "2025_midterm_003":
            r["corrected_output"] = FIX_003
            r["correction_violations"] = []
            print(f"  [fix] {tid}  -- triangle enumeration (Heron, fabs collinear check)")
        elif tid in ("2022_exam2_002", "2023_exam2_002"):
            r["corrected_output"] = FIX_TOOLKIT
            r["correction_violations"] = []
            print(f"  [fix] {tid}  -- geometry toolkit (area + distances + lines)")

    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
        encoding="utf-8",
    )
    print(f"  Updated: {path}")
    print(f"  Total records: {len(records)}")


if __name__ == "__main__":
    main()
