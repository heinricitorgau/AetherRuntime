2. Write a function that takes an integer n and returns the alternating sum of squares from 1 to n: [1/1^2 - 1/2^2 + 1/3^2 - ... + (-1)^(n+1)*1/n^2]. The requirements for this program are as follows: you need to pass an array and n to the function, which will generate an array of size n where the element at index i-1 stores the cumulative sum up to i (where i = 1, 2, ..., n). You also need a function that takes an array and its size, and returns the maximum value in the array. Finally, you should have a main function that reads n, processes the array generation through the functions, and prints out the array elements and the maximum value.

Possible execution result:

Enter n: 4
The array elements are: 1.000000 0.750000 0.861111 0.798611
The minimum of the array elements is 0.750000

Required features:
  - Function returns 1/1^2 - 1/2^2 + ... + (-1)^(n+1)/n^2
  - Fill array with running partial sums
  - Return array extremum
  - main reads n and prints elements + extremum

Sample input:
4

Expected output contains: 0.750000, array elements
