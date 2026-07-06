3. Reference point structure: 
```typedef struct {
    double x, y;
} Point;```

Write a function to read an array of points from a file and print the array. The function should find and display the pair of points that are farthest apart and their corresponding distance, as well as the pair of points that are closest together and their corresponding distance. Include a main function to utilize all these functions. The format of the input file is as follows:

```
-1 2 3 6 -3 -5
-1 0 10 -24
```

Possible execution result:

Enter the file name: points.txt
The points are: (-1.00, 2.00), (3.00, 6.00), (-3.00, -5.00), (-1.00, 0.00), (10.00, -24.00), (3.00, 6.00) and (10.00, -24.00) have the largest distance 30.8058436, (-1.00, 2.00)and (-1.00, 0.00) has the shortest distance 2.00

Required features:
  - Point struct with x,y
  - Read point array from file
  - Print the point array
  - Find farthest and closest point pairs with distances
  - main uses all functions

Sample input:
points.txt

Expected output contains: largest distance, shortest distance
