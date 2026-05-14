#include <stdio.h>
#include <stdlib.h>

int main() {
    int n;
    printf("Welcome to the Tug of War Game!\n");
    
    // Read winning distance n
    printf("Enter the winning distance (n): ");
    scanf("%d", &n);
    
    // Display the tug-war track from -n to n
    printf("Tug, War, choice\n");
    for (int i = -n; i <= n; i++) {
        if (i == 0) {
            printf("   |   %d\n", i);
        } else {
            printf("%4d|   %d\n", i, i);
        }
    }
    
    // Read player choice for stone, scissors, or paper
    char playerChoice;
    printf("\nEnter your choice (S for Stone, P for Paper, C for Scissors): ");
    scanf(" %c", &playerChoice);
    
    // Generate or otherwise select a computer choice
    srand(time(NULL));
    int computerChoice = rand() % 3 + 1; // 1: Stone, 2: Paper, 3: Scissors
    
    // Decide draw/player win/computer win
    char result;
    if (playerChoice == 'S' && computerChoice == 3) {
        result = 'P';
    } else if (playerChoice == 'P' && computerChoice == 1) {
        result = 'S';
    } else if (playerChoice == 'C' && computerChoice == 2) {
        result = 'P';
    } else if (playerChoice == computerChoice) {
        result = 'D';
    } else {
        result = 'C';
    }
    
    // Update the current distance
    int currentDistance;
    if (result == 'S') {
        currentDistance = n + 1;
    } else if (result == 'P') {
        currentDistance = -n - 1;
    } else if (result == 'D') {
        currentDistance = 0;
    }
    
    // Loop until there is a winner
    while (currentDistance != n && currentDistance != -n) {
        printf("Tug, War, choice\n");
        for (int i = -n; i <= n; i++) {
            if (i == currentDistance) {
                printf("%4d|   %c\n", i, result);
            } else {
                printf("%4d|   %d\n", i, i);
            }
        }
        
        // Read player choice for stone, scissors, or paper
        printf("\nEnter your choice (S for Stone, P for Paper, C for Scissors): ");
        scanf(" %c", &playerChoice);
        
        // Generate or otherwise select a computer choice
        srand(time(NULL));
        computerChoice = rand() % 3 + 1; // 1: Stone, 2: Paper, 3: Scissors
        
        // Decide draw/player win/computer win
        if (playerChoice == 'S' && computerChoice == 3) {
            result = 'P';
        } else if (playerChoice == 'P' && computerChoice == 1) {
            result = 'S';
        } else if (playerChoice == 'C' && computerChoice == 2) {
            result = 'P';
        } else if (playerChoice == computerChoice) {
            result = 'D';
        } else {
            result = 'C';
        }
        
        // Update the current distance
        if (result == 'S') {
            currentDistance += n + 1;
        } else if (result == 'P') {
            currentDistance -= n - 1;
        } else if (result == 'D') {
            currentDistance = 0;
        }
    }
    
    // Print a final win or lose message
    if (currentDistance == n) {
        printf("Congratulations! You won the tug of war!\n");
    } else {
        printf("Sorry, you lost the tug of war.\n");
    }
    
    return 0;
}