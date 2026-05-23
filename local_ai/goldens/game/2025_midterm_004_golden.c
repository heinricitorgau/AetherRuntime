/*
 * 2025_midterm_004 - Game Simulation - Even/Odd Guessing
 *
 * Golden guard: compile-verified C99, no nested functions.
 * Generates five unique numbers, hides them, reads guesses, reveals picks,
 * and prints stable benchmark tokens: Numbers, Pick, win, points.
 */
#include <stdio.h>
#include <stdlib.h>

#define COUNT 5
#define MIN_VALUE 1
#define MAX_VALUE 10

int already_used(int numbers[], int length, int value) {
    for (int i = 0; i < length; i++) {
        if (numbers[i] == value) {
            return 1;
        }
    }
    return 0;
}

void generate_numbers(int numbers[]) {
    int filled = 0;
    srand(1);
    while (filled < COUNT) {
        int value = rand() % (MAX_VALUE - MIN_VALUE + 1) + MIN_VALUE;
        if (!already_used(numbers, filled, value)) {
            numbers[filled] = value;
            filled++;
        }
    }
}

void print_numbers(int numbers[], int revealed[]) {
    printf("Numbers:");
    for (int i = 0; i < COUNT; i++) {
        if (revealed[i]) {
            printf(" %d", numbers[i]);
        } else {
            printf(" *");
        }
    }
    printf("\n");
}

int main(void) {
    int numbers[COUNT];
    int revealed[COUNT] = {0};
    int revealed_count = 0;
    int score = 0;

    generate_numbers(numbers);

    while (revealed_count < COUNT) {
        int pick;
        char guess;

        print_numbers(numbers, revealed);
        printf("Pick a number: ");
        if (scanf("%d", &pick) != 1) {
            break;
        }

        if (pick < 1 || pick > COUNT) {
            printf("Pick must be between 1 and %d.\n", COUNT);
            continue;
        }

        printf("Even or Odd (E|O)? ");
        if (scanf(" %c", &guess) != 1) {
            break;
        }

        if (revealed[pick - 1]) {
            printf("That number was already revealed. points = %d\n", score);
            continue;
        }

        revealed[pick - 1] = 1;
        revealed_count++;

        int value = numbers[pick - 1];
        int even = (value % 2 == 0);
        int guessed_even = (guess == 'E' || guess == 'e');
        int guessed_odd = (guess == 'O' || guess == 'o');

        if ((even && guessed_even) || (!even && guessed_odd)) {
            score += 5;
            printf("You win 5 points. Number %d is %d.\n", pick, value);
        } else {
            printf("You do not win points. Number %d is %d.\n", pick, value);
        }
    }

    print_numbers(numbers, revealed);
    printf("You win %d points.\n", score);

    return 0;
}
