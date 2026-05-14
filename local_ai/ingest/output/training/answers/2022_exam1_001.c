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

int main() {
    int n;
    printf("Enter the value of n: ");
    scanf("%d", &n);

    double sum = 0.0;
    for (int i = 1; i <= n; ++i) {
        // Calculate the denominator
        unsigned long long denominator = factorial(i * i - i + 1);
        
        // Calculate the term with alternating sign
        double term = pow(-1, i + 1) * factorial(i) / denominator;
        
        // Add the term to the sum
        sum += term;
    }

    printf("The sum of the series is: %.10f\n", sum);

    return 0;
}