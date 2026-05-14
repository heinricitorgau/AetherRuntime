#include <stdio.h>
#include <math.h>

typedef struct Point {
    double x;
    double y;
} Point;

double distance(Point p1, Point p2) {
    return sqrt(pow(p1.x - p2.x, 2) + pow(p1.y - p2.y, 2));
}

double triangleArea(Point a, Point b, Point c) {
    double s = (distance(a, b) + distance(b, c) + distance(c, a)) / 2;
    if (s < distance(a, b) || s < distance(b, c) || s < distance(c, a)) {
        printf("Triangle cannot be formed\n");
        return -1;
    }
    return sqrt(s * (s - distance(a, b)) * (s - distance(b, c)) * (s - distance(c, a)));
}

double perimeter(Point a, Point b, Point c) {
    return distance(a, b) + distance(b, c) + distance(c, a);
}

int pointInTriangle(Point p, Point a, Point b, Point c) {
    double area1 = triangleArea(p, a, b);
    double area2 = triangleArea(p, b, c);
    double area3 = triangleArea(p, c, a);
    return fabs(area1 + area2 + area3 - triangleArea(a, b, c)) < 1e-9;
}

int main() {
    Point points[4];
    printf("Enter 4 coordinate pairs separated by spaces: ");
    for (int i = 0; i < 4; i++) {
        scanf("%lf %lf", &points[i].x, &points[i].y);
    }

    double maxDistance = -1;
    Point farthestPoint;
    for (int i = 0; i < 4; i++) {
        double dist = distance(points[0], points[i]);
        if (dist > maxDistance) {
            maxDistance = dist;
            farthestPoint = points[i];
        }
    }

    printf("Farthest point from origin: (%.2lf, %.2lf)\n", farthestPoint.x, farthestPoint.y);
    printf("Distance: %.2lf\n", maxDistance);

    double area = triangleArea(points[0], points[1], points[2]);
    if (area != -1) {
        printf("Triangle Area: %.2lf\n", area);
        printf("Perimeter: %.2lf\n", perimeter(points[0], points[1], points[2]));
    }

    if (pointInTriangle(points[3], points[0], points[1], points[2])) {
        printf("4th point is inside the triangle.\n");
    } else {
        printf("4th point is outside the triangle.\n");
    }

    return 0;
}