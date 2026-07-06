4. Establish a function that takes parameters `a`, `b`, `c`, `d`, `e`, and `x`, and returns the value of \( ax^3 + bx^2 + cx + d\sin(x) + e \). Use this function to find all real roots of the equation \( ax^3 + bx^2 + cx + d\sin(x) + e = 0 \). Your program should have a main function that reads the coefficients `a`, `b`, `c`, `d`, `e` and the initial value of `x`. It should print the equation in the format \( ax^3 + bx^2 + cx + d\sin(x) + e \), and display all real roots of the equation.

Possible execution result:

```
Read ax^3 + bx^2 + cx + dsin(x) + e and x: 1 0 1 -3 0 1
The equation is y(x) = 1.0000x^3 + 1.0000x - 3.0000sin(x).
y(1) = -0.52441295442
The roots are -1.167615, 0.0000, and 1.167615.
```

Required features:
  - Function ax^3+bx^2+cx+d*sin(x)+e
  - Find all real roots of the equation
  - main reads coefficients and initial x
  - Print equation and all real roots

Sample input:
1 0 1 -3 0 1

Expected output contains: The equation is, roots
