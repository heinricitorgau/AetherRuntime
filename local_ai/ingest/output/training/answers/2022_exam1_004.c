#include <stdio.h>
#include <stdlib.h>

#define WINNING_DISTANCE 3

void print_board(int n) {
    for (int i = -n; i <= n; i++) {
        if (i == 0) {
            printf("F");
        } else {
            printf("%d", i);
        }
    }
    printf("\n");
}

int main() {
    int n;
    printf("Welcome to the Tug War Game!\nEnter winning distance: ");
    scanf("%d", &n);

    while (1) {
        print_board(n);

        int player_choice;
        printf("Enter your choice (1=rock, 2=scissors, 3=paper): ");
        scanf("%d", &player_choice);

        if (player_choice < 1 || player_choice > 3) {
            printf("Invalid choice. Please enter 1, 2, or 3.\n");
            continue;
        }

        int computer_choice = rand() % 3 + 1;

        printf("Computer chose: ");
        switch (computer_choice) {
            case 1:
                printf("rock\n");
                break;
            case 2:
                printf("scissors\n");
                break;
            case 3:
                printf("paper\n");
                break;
        }

        int result = player_choice - computer_choice;

        if (result == 0) {
            printf("It's a tie!\n");
        } else if ((result == 1 || result == -2) && player_choice > computer_choice) {
            printf("You win!\n");
        } else if ((result == -1 || result == 2) && player_choice < computer_choice) {
            printf("Computer wins!\n");
        }

        n += result;
    }

    return 0;
}