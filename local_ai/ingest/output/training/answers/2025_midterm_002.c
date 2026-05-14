#include <stdio.h>

int main() {
    int n;
    
    // Read integer n from the user
    printf("Enter an integer n (1 to 10): ");
    scanf("%d", &n);
    
    // Check if n is within the valid range
    if (n < 1 || n > 10) {
        printf("Invalid input. Please enter a number between 1 and 10.\n");
        return 1;
    }
    
    // Generate and print each row of the triangle pattern
    for (int i = 1; i <= n; i++) {
        // Print leading spaces to center the digits
        for (int j = n - i; j > 0; j--) {
            printf(" ");
        }
        
        // Print the current row's digits
        for (int k = 0; k < i; k++) {
            printf("%d", i);
        }
        
        // Move to the next line after each row
        printf("\n");
    }
    
    return 0;
}