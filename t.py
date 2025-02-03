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
    c = [-u_olive_oil, -u_pomace_oil, -u_pko_oil, -u_rbd_oil]
    # Constraints matrix
    A_ub = [[u_olive_oil, u_pomace_oil, u_pko_oil, u_rbd_oil]]  # Total value constraint
    b_ub = [available_value]
    A_eq = [[1 if use_olive else 0, 1 if use_pomace else 0, 1 if use_pko else 0, 1 if use_rbd else 0]]  # Total oil used constraint
    b_eq = [total_oil_available]
    # Variable bounds (all must be non-negative)
    bounds = [(0, None) if use_olive else (0, 0),
              (0, None) if use_pomace else (0, 0),
              (0, None) if use_pko else (0, 0),
              (0, None) if use_rbd else (0, 0)]
    # Solve the linear programming problem using HiGHS solver
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method='highs')
    # Check if the optimization was successful and return results
    if result.success:
        return {
            "olive_oil": result.x[0] if use_olive else 0,
            "pomace_oil": result.x[1] if use_pomace else 0,
            "pko_oil": result.x[2] if use_pko else 0,
            "rbd_oil": result.x[3] if use_rbd else 0,
            "total_value_used": -result.fun
        }
    else:
        return {"error": "Optimization was not successful."}

# Example usage
u_olive_oil = 5.5
u_pomace_oil = 3
u_pko_oil = 1.3
u_rbd_oil = 1.1
available_value = 428510.55
total_oil_available = 146531.00

# Call function with specific oil usage conditions
result = optimize_oil_distribution(u_olive_oil, u_pomace_oil, u_pko_oil, u_rbd_oil, available_value, total_oil_available, use_olive=True, use_pomace=True, use_pko=True, use_rbd=True)

# Print the results
if "error" in result:
    print(result["error"])
else:
    print(f"Max olive_oil: {result['olive_oil']:.2f} units")
    print(f"Max pomace_oil: {result['pomace_oil']:.2f} units")
    print(f"Max pko_oil: {result['pko_oil']:.2f} units")
    print(f"Max rbd_oil: {result['rbd_oil']:.2f} units")
    print(f"Total value used: {result['total_value_used']:.2f}")
