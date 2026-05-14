#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int main() {
    srand(time(NULL));
    int winNumber = rand() % 36 + 1;
    int points = 0;
    int totalGuesses = 0;

    printf("Welcome to the Roulette-style Guessing Game!\n");
    printf("Your initial point is: %d\n", points);
    printf("Choose your guess:\n");
    printf("O - Odd\nE - Even\nL - Left (1-18)\nC - Center (19-36)\nR - Right (19-36)\nN - Exact number\n");

    while (1) {
        char choice;
        int riskPoints;

        printf("Enter your guess: ");
        scanf(" %c", &choice);
        printf("Enter the points at risk: ");
        scanf("%d", &riskPoints);

        totalGuesses++;

        if (choice == 'O') {
            if (winNumber % 2 != 0) {
                points += riskPoints;
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        } else if (choice == 'E') {
            if (winNumber % 2 == 0) {
                points += riskPoints;
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        } else if (choice == 'L') {
            if (winNumber >= 1 && winNumber <= 18) {
                points += riskPoints;
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        } else if (choice == 'C') {
            if (winNumber >= 19 && winNumber <= 36) {
                points += riskPoints;
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        } else if (choice == 'R') {
            if (winNumber >= 19 && winNumber <= 36) {
                points += riskPoints;
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        } else if (choice == 'N') {
            if (winNumber == winNumber) {
                points += riskPoints * 36; // Assuming a multiplier for exact number wins
                printf("You won! Your new point is: %d\n", points);
            } else {
                points -= riskPoints;
                printf("You lost. Your new point is: %d\n", points);
            }
        }

        char continueChoice;
        printf("Do you want to continue? (Y/N): ");
        scanf(" %c", &continueChoice);

        if (continueChoice != 'Y') {
            break;
        }
    }

    printf("Total number of guesses: %d\n", totalGuesses);
    printf("Final points: %d\n", points);

    return 0;
}