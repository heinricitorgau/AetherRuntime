#include <stdio.h>

int main() {
    int n;
    
    // Read integer input n
    printf("Enter an integer n: ");
    scanf("%d", &n);
    
    // Generate the expanding upper rows
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d", j);
        }
        printf("\n");
    }
    
    // Generate the middle numeric row
    printf("%d\n", n * 2 - 1);
    
    // Generate the shrinking lower rows
    for (int i = n - 1; i >= 1; i--) {
        for (int j = 1; j <= i; j++) {
            printf("%d", j);
        }
        printf("\n");
    }
    
    return 0;
}