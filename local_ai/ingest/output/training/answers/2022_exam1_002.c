#include <stdio.h>

int main() {
    int n;
    
    // Read integer n from user
    printf("Enter the value of n: ");
    scanf("%d", &n);
    
    // Generate top half (expanding)
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d ", j);
        }
        for (int k = i - 2; k >= 0; k--) {
            printf("%d ", k + 1);
        }
        printf("\n");
    }
    
    // Generate middle row
    for (int i = 1; i <= n; i++) {
        printf("%d", i);
    }
    printf("\n");
    
    // Generate bottom half (contracting)
    for (int i = n - 1; i >= 1; i--) {
        for (int j = 1; j <= i; j++) {
            printf("%d ", j);
        }
        for (int k = i - 2; k >= 0; k--) {
            printf("%d ", k + 1);
        }
        printf("\n");
    }
    
    return 0;
}