#include <stdio.h>
#include <math.h>

// Function to calculate factorial of a number
unsigned long long factorial(int num) {
    unsigned long long result = 1;
    for (int i = 2; i <= num; ++i) {
        result *= i;
    }
    return result;
}

// Function to compute the series sum
double computeSeriesSum(int n) {
    double sum = 0.0;
    int sign = 1;
    for (int k = 1; k <= n; ++k) {
        unsigned long long term = factorial(k);
        sum += sign * ((double)term / (k * k + k + 1));
        sign *= -1; // Alternate the sign
    }
    return sum;
}

int main() {
    int n;
    printf("Enter an integer n: ");
    scanf("%d", &n);

    double result = computeSeriesSum(n);
    printf("f(%d) = %.10lf\n", n, result);

    return 0;
}