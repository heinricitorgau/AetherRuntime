#include <stdio.h>
#include <math.h>

// Function to calculate the Euclidean distance between two points
double distance(double x1, double y1, double x2, double y2) {
    return sqrt((x2 - x1) * (x2 - x1) + (y2 - y1) * (y2 - y1));
}

// Function to find the farthest point from the origin
void findFarthestPoint(double points[][2], int n, double* maxDistance, int* farthestIndex) {
    for (int i = 0; i < n; i++) {
        double dist = distance(0, 0, points[i][0], points[i][1]);
        if (dist > *maxDistance) {
            *maxDistance = dist;
            *farthestIndex = i;
        }
    }
}

// Function to calculate the perimeter of a triangle
double calculatePerimeter(double points[][2], int n) {
    double perimeter = 0.0;
    for (int i = 0; i < n - 1; i++) {
        perimeter += distance(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1]);
    }
    perimeter += distance(points[n - 1][0], points[n - 1][1], points[0][0], points[0][1]);
    return perimeter;
}

// Function to calculate the area of a triangle using Heron's formula
double calculateArea(double points[][2], int n) {
    if (n < 3) {
        printf("No triangle can be formed.\n");
        return -1.0;
    }
    double side1 = distance(points[0][0], points[0][1], points[1][0], points[1][1]);
    double side2 = distance(points[1][0], points[1][1], points[2][0], points[2][1]);
    double side3 = distance(points[2][0], points[2][1], points[0][0], points[0][1]);

    double s = (side1 + side2 + side3) / 2.0;
    return sqrt(s * (s - side1) * (s - side2) * (s - side3));
}

// Function to check if a point is inside or outside the triangle
int isPointInsideTriangle(double points[][2], int n, double x, double y) {
    // Check for collinearity first
    for (int i = 0; i < n - 1; i++) {
        double area = calculateArea(points[i], points[i + 1], points[(i + 2) % n]);
        if (area == 0.0) {
            printf("No triangle can be formed.\n");
            return -1;
        }
    }

    // Check if the point is inside the triangle
    int count = 0;
    for (int i = 0; i < n; i++) {
        double crossProduct = (points[i][0] - x) * (points[(i + 1) % n][1] - y) -
                            (points[(i + 1) % n][0] - x) * (points[i][1] - y);
        if (crossProduct > 0.0) {
            count++;
        }
    }

    return (count % 2 == 1) ? 1 : 0;
}

int main() {
    double points[4][2];
    int n = 4;

    // Read four coordinate pairs
    for (int i = 0; i < n; i++) {
        scanf("%lf %lf", &points[i][0], &points[i][1]);
    }

    // Print the four points
    printf("The four points are:\n");
    for (int i = 0; i < n; i++) {
        printf("(%lf, %lf)\n", points[i][0], points[i][1]);
    }

    // Find the farthest point from the origin
    double maxDistance = 0.0;
    int farthestIndex;
    findFarthestPoint(points, n, &maxDistance, &farthestIndex);
    printf("The farthest point from (0,0) is (%lf, %lf) with a distance of %.4f.\n", points[farthestIndex][0], points[farthestIndex][1], maxDistance);

    // Calculate the perimeter and area of the triangle formed by the first three points
    double perimeter = calculatePerimeter(points, 3);
    double area = calculateArea(points, 3);
    printf("The perimeter of the triangle is %.4f.\n", perimeter);
    printf("The area of the triangle is %.4f.\n", area);

    // Check whether the fourth point is inside or outside the triangle
    int result = isPointInsideTriangle(points, n, points[3][0], points[3][1]);
    if (result == 1) {
        printf("The fourth point is inside the triangle.\n");
    } else if (result == 0) {
        printf("The fourth point is outside the triangle.\n");
    }

    return 0;
}