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
    printf("Enter an integer n between 1 and 20: ");
    scanf("%d", &n);

    if (n < 1 || n > 20) {
        printf("Invalid input. Please enter a number between 1 and 20.\n");
        return 1;
    }

    double sum = 0.0;
    for (int i = 1; i <= n; ++i) {
        int sign = (i % 2 == 0) ? -1 : 1;
        unsigned long long term = factorial(i);
        sum += sign * ((double)term / (i * i + i + 1));
    }

    printf("The sum of the series is: %.15f\n", sum);

    return 0;
}