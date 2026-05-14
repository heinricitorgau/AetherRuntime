#include <stdio.h>
#include <math.h>

int main() {
    int n;
    double sum = 0.0;

    printf("Enter an integer n: ");
    scanf("%d", &n);

    for (int i = 1; i <= n; i++) {
        double numerator = 2 * i + 1;
        double denominator = i * i - 1;
        double term = numerator / denominator;

        if (i % 2 != 0) {
            sum += term;
        } else {
            sum -= term;
        }
    }

    printf("The sum of the series is: %.6f\n", sum);

    return 0;
}