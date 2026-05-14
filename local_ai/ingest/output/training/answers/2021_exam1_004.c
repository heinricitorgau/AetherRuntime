#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int main() {
    srand(time(NULL));
    
    int guess;
    int number;
    int points = 0;
    char playAgain;

    while (1) {
        printf("Enter your guess (low, mid, high, odd/even, single number): ");
        scanf("%s", &guess);

        number = rand() % 12 + 1;

        if (strcmp(guess, "low") == 0 || strcmp(guess, "mid") == 0 || strcmp(guess, "high") == 0) {
            points += (number >= 5 && number <= 8) ? 3 : 1;
        } else if (strcmp(guess, "odd") == 0 || strcmp(guess, "even") == 0) {
            points += (number % 2 == 0) ? 2 : 1;
        } else if (guess[0] >= '1' && guess[0] <= '9') {
            int singleNumber = guess[0] - '0';
            points += (singleNumber == number) ? 12 : 0;
        }

        printf("Generated number: %d\n", number);
        printf("Points: %d\n", points);

        printf("Do you want to play again? (y/n): ");
        scanf("%s", &playAgain);
        if (strcmp(playAgain, "n") == 0) {
            break;
        }
    }

    printf("Final points: %d\n", points);

    return 0;
}