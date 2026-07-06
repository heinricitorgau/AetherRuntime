5. Establish a Poker Match guessing game class with the following rules and requirements:
1. Write a function that takes an integer n (n < 6) and randomly fills a grid of 2n^2 elements with different cards from a standard deck of 52 playing cards. The card suits are represented by Spades (S), Hearts (H), Diamonds (D), and Clubs (C). The card values range from 2 to 14, where 2-10 represent their face value, T represents 10, J represents Jack, Q represents Queen, K represents King, and A represents Ace.
2. Players and the computer take turns selecting a pair of cards by entering coordinates. Once a coordinate is selected, it cannot be chosen again.
3. Cards are initially hidden with asterisks (*). They will remain permanently revealed after being selected.
4. Scoring rules: If the two selected cards have the same value, the player earns 20 points; if they have the same suit but different values, the player earns 10 points; otherwise, the player earns 0 points.
5. The game ends when there are no more selectable cards. The final results are summarized, and the winner is declared.
6. Write a main function to demonstrate the usage of this class.

Possible execution result:

Enter n    : 2
 * * * *
 * * * *
Your picks :1 1 1 2
 KS KH * *
 *  *  * *
Your cards : KS KH Computer's cards : 8H 2D
Your points: 20    Computer's points: 0
Your picks : 1 3 1 4
 KS KH 7C 9C
 JD JH 8H 2D
Your cards : 7C 9C Computer's cards : JD JH
Your points: 30    Computer's points: 20
You win the game

Required features:
  - Fill 2n^2 grid with distinct cards
  - Turn-based coordinate picking
  - Hidden cards revealed on pick
  - Scoring by rank/suit match
  - Announce winner

Sample input:
2\n1 1 1 2\n1 3 1 4

Expected output contains: points, win
