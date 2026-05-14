#include <stdio.h>

int main() {
    int n;
    
    // Read integer input n
    printf("Enter an integer n: ");
    scanf("%d", &n);
    
    // Generate the arrow pattern
    for (int i = 0; i <= n; i++) {
        if (i == n) {
            // Print center row with ascending then descending digits
            for (int j = 1; j <= n; j++) {
                printf("%d", j);
            }
            printf("\n");
        } else {
            // Print upper and lower rows with correct spacing
            int numDigits = i + 1;
            int start = 1;
            int end = numDigits - 1;
            
            for (int j = 0; j < numDigits; j++) {
                printf("%d", start);
                if (j != numDigits - 1) {
                    printf(" ");
                }
            }
            
            // Print descending digits
            for (int j = end; j >= 1; j--) {
                printf("%d", j);
                if (j != 1) {
                    printf(" ");
                }
            }
            
            printf("\n");
        }
    }
    
    return 0;
}