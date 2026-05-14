#include <stdio.h>
#include <math.h>

// Function to compute n!
long long factorial(int n) {
    if (n <= 1) return 1;
    long long result = 1;
    for (int i = 2; i <= n; ++i) {
        result *= i;
    }
    return result;
}

// Function to calculate the series sum
double f(int n) {
    double sum = 0.0;
    int sign = 1;
    for (int k = 1; k <= n; ++k) {
        long long term = factorial(k);
        sum += sign * ((double)term / (k * k - k + 1));
        sign *= -1; // Alternate signs
    }
    return sum;
}

int main() {
    int n;
    printf("Enter an integer n: ");
    scanf("%d", &n);

    double result = f(n);
    printf("f(%d) = %.15lf\n", n, result);

    return 0;
}