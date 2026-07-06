4. Consider the following Point structure: 
```typedef struct { double x, y;} Point;```

Consider the LineEq structure for a linear equation ax + by = c:
```typedef struct { double a, b, c; } LineEq;```

And consider the Parabola structure for a parabolic equation y = ax^2 + bx + c:
```{ double a, b, c; } Parabola;```

Write a function that takes two points and returns a linear equation. The function should print the linear equation in the format `ax + by = c`. Write another function that takes a parabolic equation and prints it in the format `y = ax^2 + bx + c`. Write a third function that takes a line equation and a parabola, and returns their intersection point(s). Read from a file containing multiple pairs of points and parabolic equations (coefficients a, b, c), and use the above functions to process each pair. The file format for input data is as follows:
```
0 0 2 2 1 0 0
0 -1 2 -1 1 0 0
```

Hint: The equation of the line passing through points (x1, y1) and (x2, y2) can be represented as {(y1 - y2)*x + (x2 - x1)*y = x2*y1 - x1*y2}. Substitute the parabolic equation into the linear equation, and solve the resulting quadratic equation.

Possible output:
```
The line equation is -2.0000x + 2.0000y = 0.0000.
The parabola equation is y = 1.0000x^2 + 0.0000x + 0.0000.
The intersection point(s) of the line and the parabola are (0.0000, 0.0000) and (1.0000, 1.0000).
The line equation is 0.0000x + 2.0000y = -2.0000.
The parabola equation is y = 1.0000x^2 + 0.0000x + 0.0000.
The line and the parabola have no intersection point.
```

Required features:
  - Line equation from two points
  - Print line ax+by=c
  - Print parabola y=ax^2+bx+c
  - Intersection of line and parabola
  - Read multiple records from file

Sample input:
0 0 2 2 1 0 0\n0 -1 2 -1 1 0 0

Expected output contains: The line equation is, The parabola equation is, no intersection point
