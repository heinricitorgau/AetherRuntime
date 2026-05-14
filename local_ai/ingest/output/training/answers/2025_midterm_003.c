#include <stdio.h>
#include <math.h>

// Function to calculate the distance between two points
double distance(double x1, double y1, double x2, double y2) {
    return sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
}

// Function to check if three points are collinear
int isCollinear(double x1, double y1, double x2, double y2, double x3, double y3) {
    return (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)) == 0;
}

// Function to calculate the area of a triangle using Heron's formula
double heronsFormula(double a, double b, double c) {
    double s = (a + b + c) / 2.0;
    return sqrt(s * (s - a) * (s - b) * (s - c));
}

int main() {
    // Read coordinates of 4 points
    double x1, y1, x2, y2, x3, y3, x4, y4;
    printf("Enter the coordinates of 4 points: ");
    scanf("%lf %lf %lf %lf %lf %lf %lf %lf", &x1, &y1, &x2, &y2, &x3, &y3, &x4, &y4);

    // Generate all 3-point combinations
    printf("Triangles:\n");
    for (int i = 0; i < 4; i++) {
        for (int j = i + 1; j < 4; j++) {
            for (int k = j + 1; k < 4; k++) {
                double a = distance(x1, y1, x2, y2);
                double b = distance(x2, y2, x3, y3);
                double c = distance(x3, y3, x4, y4);

                // Check if points are collinear
                if (isCollinear(x1, y1, x2, y2, x3, y3) || 
                    isCollinear(x2, y2, x3, y3, x4, y4) || 
                    isCollinear(x3, y3, x4, y4, x1, y1)) {
                    printf("Collinear points: (%.3f, %.3f), (%.3f, %.3f), (%.3f, %.3f)\n", 
                           x1, y1, x2, y2, x3, y3);
                } else {
                    // Calculate area using Heron's formula
                    double area = heronsFormula(a, b, c);
                    printf("Area: %.3f\n", area);
                }
            }
        }
    }

    return 0;
}