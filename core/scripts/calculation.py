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
    con1 = {'type': 'eq', 'fun': lambda x: Z1 - x[0] * Y1 - x[1] * Y2}
    con2 = {'type': 'eq', 'fun': lambda x: Z2 - x[0] - x[1]}
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
def optimize_product_distribution(pko_unit, veg_oil_unit, available_qty, available_value, is_pko):
    pko, veg_oil = find_values(float(pko_unit), float(veg_oil_unit), float(available_value), float(available_qty))
    if is_pko:
        return {
            'pko': {"quantity": pko, "value": Decimal(pko) * Decimal(pko_unit)},
            'veg_oil': {"quantity": veg_oil, "value": Decimal(veg_oil) * Decimal(veg_oil_unit)},
            'get_rbd': {"quantity": 0, "value": 0}
        }
    else:
        return {
            'pko': {"quantity": 0, "value": 0},
            'veg_oil': {"quantity": veg_oil, "value": Decimal(veg_oil) * Decimal(veg_oil_unit)},
            'get_rbd': {"quantity": pko, "value": Decimal(pko) * Decimal(pko_unit)}
        }


# write a python function to find X1 & X2
# X1*Y1 + X2*Y2<=Z1
# X1 + X2<=Z2
# X1>=0
# X2>=0
# X1+X2 should be almost equal to Z2
# X1*Y1 + X2*Y2 should me almost equal to Z1

import numpy as np
from scipy.optimize import linprog

import numpy as np
from scipy.optimize import linprog


def split_quantity_with_flags(total_milk, available_value, SWP_price=1, cheese_unit=5.5, wpc_unit=15, use_swp=False,
                              use_cheese=False, use_wpc=False):
    SWP_price = SWP_price
    CHEESE_price = cheese_unit
    WPC_min_price = 0
    WPC_max_price = wpc_unit
    if use_swp and use_cheese and use_wpc:
        c = [-SWP_price, -CHEESE_price, -WPC_max_price, 0, 0]
        A_eq = [
            [1, 1, 1, 0, 0],
            [SWP_price, CHEESE_price, WPC_max_price, 0, 0],
            [-1, 0, 0, 1, 0],
            [0, -1, 0, 0, 1]
        ]
        b_eq = [total_milk, available_value, 0, 0]
        # Set realistic bounds to avoid unbounded variables
        bounds = [(0, None), (0, None), (0, None), (0, total_milk), (0, available_value)]
        # Cheese must have a minimum value if selected
        if use_cheese:
            bounds[1] = (0.0001, None)
        # Solve using the 'highs' solver
        result = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
        if result.success:
            SWP = result.x[0]
            CHEESE = result.x[1]
            WPC = result.x[2]
            return SWP, CHEESE, WPC
        else:
            print("Linear programming failed:", result.message)
            return None
    else:
        c = [-SWP_price, -CHEESE_price, -WPC_max_price]
        A_ub = []
        b_ub = []
        A_ub.append([1 if use_swp else 0, 1 if use_cheese else 0, 1 if use_wpc else 0])
        b_ub.append(total_milk)
        A_ub.append([SWP_price if use_swp else 0, CHEESE_price if use_cheese else 0, WPC_max_price if use_wpc else 0])
        b_ub.append(available_value)
        bounds = []
        if use_swp:
            bounds.append((0, total_milk))
        else:
            bounds.append((0, 0))
        if use_cheese:
            bounds.append((0.0001, total_milk))
        else:
            bounds.append((0, 0))
        if use_wpc:
            bounds.append((0, total_milk))
        else:
            bounds.append((0, 0))
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if result.success:
            SWP, CHEESE, WPC = result.x
            return SWP, CHEESE, WPC
        else:
            print("Linear programming failed:", result.message)
            return None


from scipy.optimize import linprog

from scipy.optimize import linprog

def optimize_oil_distribution(
    u_olive_oil, u_pomace_oil, u_pko_oil, u_rbd_oil,
    available_value, total_oil_available,
    use_olive=True, use_pomace=True, use_pko=True, use_rbd=True
):
    # Apply selection by setting unit price to zero for disallowed oils
    u_olive_oil = u_olive_oil if use_olive else 0
    u_pomace_oil = u_pomace_oil if use_pomace else 0
    u_pko_oil = u_pko_oil if use_pko else 0
    u_rbd_oil = u_rbd_oil if use_rbd else 0

    # Objective function coefficients (maximize total value, so negate for minimization)
    c = [-u_olive_oil, -u_pomace_oil, -u_pko_oil, -u_rbd_oil, 0]  # Slack oil is neutral

    # Constraints matrix
    A_ub = [[u_olive_oil, u_pomace_oil, u_pko_oil, u_rbd_oil, 0]]  # Total value constraint
    b_ub = [available_value]

    A_eq = [[1 if use_olive else 0, 1 if use_pomace else 0, 1 if use_pko else 0, 1 if use_rbd else 0, 1]]  # Total oil used constraint
    b_eq = [total_oil_available]

    # Variable bounds (all must be non-negative)
    bounds = [(0, None) if use_olive else (0, 0),
              (0, None) if use_pomace else (0, 0),
              (0, None) if use_pko else (0, 0),
              (0, None) if use_rbd else (0, 0),
              (0, total_oil_available)]  # Slack oil can only take up to the max available

    # Solve the linear programming problem using HiGHS solver
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')

    # Check if the optimization was successful and return results
    if result.success:
        return {
            "olive_oil": result.x[0] if use_olive else 0,
            "pomace_oil": result.x[1] if use_pomace else 0,
            "pko_oil": result.x[2] if use_pko else 0,
            "rbd_oil": result.x[3] if use_rbd else 0,
            "slack_oil": result.x[4],  # How much oil was unused (if any)
            "total_value_used": -result.fun
        }
    else:
        return {"error": "Optimization was not successful."}

