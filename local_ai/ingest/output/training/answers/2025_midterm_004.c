#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define NUM_NUMBERS 5

void generateRandomNumbers(int numbers[]) {
    srand(time(NULL));
    for (int i = 0; i < NUM_NUMBERS; i++) {
        numbers[i] = rand() % 10 + 1;
    }
}

void hideNumbers(char hiddenNumbers[], int numbers[]) {
    for (int i = 0; i < NUM_NUMBERS; i++) {
        hiddenNumbers[i] = '*';
    }
}

void displayGame(int numbers[], char hiddenNumbers[], int score) {
    printf("Numbers: ");
    for (int i = 0; i < NUM_NUMBERS; i++) {
        printf("%c ", hiddenNumbers[i]);
    }
    printf("\nScore: %d\n", score);
}

int main() {
    int numbers[NUM_NUMBERS];
    char hiddenNumbers[NUM_NUMBERS];
    int score = 0;
    int position, guess;

    generateRandomNumbers(numbers);
    hideNumbers(hiddenNumbers, numbers);

    while (1) {
        displayGame(numbers, hiddenNumbers, score);

        printf("Pick a number (1-%d): ", NUM_NUMBERS);
        scanf("%d", &position);
        if (position < 1 || position > NUM_NUMBERS) {
            printf("Invalid input. Please enter a number between 1 and %d.\n", NUM_NUMBERS);
            continue;
        }

        printf("Guess even or odd (E/O): ");
        scanf(" %c", &guess);

        if ((numbers[position - 1] % 2 == 0 && guess == 'E') || 
            (numbers[position - 1] % 2 != 0 && guess == 'O')) {
            score += 5;
            hiddenNumbers[position - 1] = numbers[position - 1];
        }

        if (score >= NUM_NUMBERS * 5) {
            printf("Congratulations! You've revealed all the numbers.\n");
            break;
        }
    }

    return 0;
}