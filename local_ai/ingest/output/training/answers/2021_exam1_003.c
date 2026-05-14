#include <stdio.h>
#include <math.h>

// Function to calculate the area of a triangle formed by line ax + by = c with x-axis and y-axis
double triangleAreaFromLine(double a, double b, double c) {
    if (a == 0 || b == 0) return 0;
    double x = c / a;
    double y = c / b;
    return 0.5 * x * y;
}

// Function to calculate the distance from point (x₀, y₀) to line ax + by = c
double distanceFromPointToLine(double x0, double y0, double a, double b, double c) {
    return fabs(a * x0 + b * y0 - c) / sqrt(a * a + b * b);
}

// Function to calculate the area of a triangle formed by three points (x1, y1), (x2, y2), (x3, y3)
double triangleAreaFromPoints(double x1, double y1, double x2, double y2, double x3, double y3) {
    double a = sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
    double b = sqrt((x3 - x2) * (x3 - x2) + (y3 - y2) * (y3 - y2));
    double c = sqrt((x1 - x3) * (x1 - x3) + (y1 - y3) * (y1 - y3));

    if (a + b <= c || a + c <= b || b + c <= a) return 0;

    double s = (a + b + c) / 2;
    return sqrt(s * (s - a) * (s - b) * (s - c));
}

// Function to show the line equation passing through two points (x1, y1), (x2, y2)
void showLineEquation(double x1, double y1, double x2, double y2) {
    if (x1 == x2) {
        printf("y = %.2f\n", y1);
    } else if (y1 == y2) {
        printf("x = %.2f\n", x1);
    } else {
        double m = (y2 - y1) / (x2 - x1);
        double c = y1 - m * x1;
        printf("y = %.2fx + %.2f\n", m, c);
    }
}

int main() {
    double x1, y1, x2, y2, x3, y3;

    // Read input points
    scanf("%lf %lf %lf %lf %lf %lf", &x1, &y1, &x2, &y2, &x3, &y3);

    // Calculate and print the area of the triangle formed by line ax + by = c with x-axis and y-axis
    double areaFromLine = triangleAreaFromLine(x1, y1, 0);
    printf("Area from line: %.2f\n", areaFromLine);

    // Calculate and print the distance from point (x₀, y₀) to line ax + by = c
    double distance = distanceFromPointToLine(x1, y1, x2, y2, 0);
    printf("Distance from point (%.2f, %.2f) to line: %.2f\n", x1, y1, distance);

    // Calculate and print the area of the triangle formed by three points
    double areaFromPoints = triangleAreaFromPoints(x1, y1, x2, y2, x3, y3);
    printf("Area from points (%.2f, %.2f), (%.2f, %.2f), (%.2f, %.2f): %.2f\n", x1, y1, x2, y2, x3, y3, areaFromPoints);

    // Show the line equation passing through two points
    showLineEquation(x1, y1, x2, y2);

    return 0;
}