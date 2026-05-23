/* 2025_midterm_003 - Geometry - Triangle Enumeration
 *
 * Golden repair: human-curated, compile-verified, runtime-verified.
 *
 * Read 4 points, enumerate all C(4,3)=4 triangles.
 * For each combination: check collinearity, compute area via Heron's formula.
 *
 * Sample input:  0 0 0 3 4 0 4 3
 * Expected output contains: area, 6.000
 */
#include <stdio.h>
#include <math.h>

double distance(double x1, double y1, double x2, double y2) {
    return sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
}

int isCollinear(double x1, double y1, double x2, double y2,
                double x3, double y3) {
    double cross = x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2);
    return fabs(cross) < 1e-9;
}

double triangleArea(double a, double b, double c) {
    double s = (a + b + c) / 2.0;
    return sqrt(s * (s - a) * (s - b) * (s - c));
}

int main(void) {
    double x[4], y[4];

    for (int i = 0; i < 4; i++) {
        scanf("%lf %lf", &x[i], &y[i]);
    }

    for (int i = 0; i < 4; i++) {
        for (int j = i + 1; j < 4; j++) {
            for (int k = j + 1; k < 4; k++) {
                if (isCollinear(x[i], y[i], x[j], y[j], x[k], y[k])) {
                    printf("Points (%g,%g) (%g,%g) (%g,%g) are collinear\n",
                           x[i], y[i], x[j], y[j], x[k], y[k]);
                } else {
                    double a = distance(x[i], y[i], x[j], y[j]);
                    double b = distance(x[j], y[j], x[k], y[k]);
                    double c = distance(x[k], y[k], x[i], y[i]);
                    double area = triangleArea(a, b, c);
                    printf("Triangle (%g,%g) (%g,%g) (%g,%g) area = %.3f\n",
                           x[i], y[i], x[j], y[j], x[k], y[k], area);
                }
            }
        }
    }

    return 0;
}
