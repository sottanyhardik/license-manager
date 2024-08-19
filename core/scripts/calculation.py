from decimal import Decimal

from scipy.optimize import minimize
import numpy as np


def calculate_X2(Y2, Z1, Z2):
    X2_max = Z1 / Y2
    X2_actual = min(X2_max, Z2)  # X1 + X2 must also be less than or equal to Z2
    return X2_actual


def find_values(Y1, Y2, Z1, Z2):
    x0 = np.array([0, 0])  # initial values
    # Constraints
    con1 = {'type': 'ineq', 'fun': lambda x: Z1 - x[0] * Y1 - x[1] * Y2}
    con2 = {'type': 'ineq', 'fun': lambda x: Z2 - x[0] - x[1]}
    cons = ([con1, con2])
    # Bounds
    bnds = ((0, None), (0, None))
    # Objective to minimize
    objective = lambda x: (Z2 - (x[0] + x[1])) ** 2 + (Z1 - (x[0] * Y1 + x[1] * Y2)) ** 2
    # Call scipy's minimize function
    res = minimize(objective, x0, bounds=bnds, constraints=cons)
    if res.success:
        X1, X2 = res.x
        if X1 == 0:
            return 0, calculate_X2(11, Z1, Z2)
        return X1, X2
    else:
        return 0, calculate_X2(Y2, Z1, Z2)


# call function with specific values
def optimize_product_distribution(pko_unit, veg_oil_unit, pko_quantity, available_value):
    pko, veg_oil = find_values(float(pko_unit), float(veg_oil_unit), float(available_value), float(pko_quantity))
    return {
        'pko': {"quantity": pko, "value": Decimal(pko) * pko_unit},
        'veg_oil': {"quantity": veg_oil, "value": Decimal(veg_oil) * veg_oil_unit},
        'get_rbd': {"quantity": 0, "value": 0}
    }

# write a python function to find X1 & X2
# X1*Y1 + X2*Y2<=Z1
# X1 + X2<=Z2
# X1>=0
# X2>=0
# X1+X2 should be almost equal to Z2
# X1*Y1 + X2*Y2 should me almost equal to Z1
