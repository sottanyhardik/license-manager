import numpy as np
def solve_equations(y1, y2, Z1, Z2):
    # Coefficients of the equations
    a = np.array([[y1, y2], [1, 1]], dtype=float)
    # Right-hand side of the equations
    b = np.array([Z1, Z2], dtype=float)
    # Solve the equations
    x = np.linalg.solve(a, b)

    # Check and enforce value constraints for x1 and x2
    x = [0 if xi < 0 else xi for xi in x]

    return x


# call function with specific values
def optimize_product_distribution(pko_quantity, available_value):
    pko, veg_oil = solve_equations(1, 9, available_value,pko_quantity)
    return {
        'pko': {"quantity": pko, "value": pko*1},
        'veg_oil': {"quantity": veg_oil,
                    "value": veg_oil*9}
    }