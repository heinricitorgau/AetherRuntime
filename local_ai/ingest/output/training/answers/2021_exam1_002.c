#include <stdio.h>

int main() {
    int n;
    
    // Read integer n
    printf("Enter an integer n (1-10): ");
    scanf("%d", &n);
    
    // Generate top half of arrow (expanding)
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= i; j++) {
            printf("%d", j);
        }
        for (int k = i - 2; k >= 0; k--) {
            printf("%d", k + 1);
        }
        printf("\n");
    }
    
    // Generate bottom half of arrow (contracting)
    for (int i = n - 1; i > 0; i--) {
        for (int j = 1; j <= i; j++) {
            printf("%d", j);
        }
        for (int k = i - 2; k >= 0; k--) {
            printf("%d", k + 1);
        }
        printf("\n");
    }
    
    return 0;
}