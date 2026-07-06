5. Write a card guessing game according to the following rules:
1. Input `n` (`n <= 26`) and generate an `n * 2n` board, randomly pairing different letters (matching pairs) on the board, with all letters hidden when the game starts.
2. The computer randomly selects `n` letters for the player to guess.
3. The user chooses 2n letter positions (input coordinates to flip the cards).
4. Each time the user picks n pairs of letters, if a correct match is made and the letter is one of the computer's designated target letters, the player earns corresponding points. The scoring method is: letters 'a' to 'z' correspond to 1 to 26 points respectively.
5. Display the final result of the game.

Possible execution results:

Enter n: 3
* * * * * *
* * * * * *
* * * * * *
Find the number C, E, and H.
Select 6 alphabets: 1 2 2 4 3 2 2 3 3 6 1 4
* C * G * *
* * E F * *
* D * * * E
You guess 1 pair (E, E) and get 10 points.

Required features:
  - Read n (n<=26) and build n x 2n board of paired letters
  - Computer picks n target letters
  - User flips 2n positions by coordinate
  - Score matched target letters by a=1..z=26
  - Show final result

Sample input:
3\n1 2 2 4 3 2 2 3 3 6 1 4

Expected output contains: points, pairs
