from scipy.optimize import linprog

def allocate_priority_oils_with_min_pomace(total_qty, total_cif_budget,
                                           olive_cif=5.0, rbd_cif=1.1,
                                           pomace_cif=3.0, pko_cif=1.2):
    """
    Allocates oil quantities:
    - Strictly matches total quantity and CIF value
    - RBD > Pomace > Olive > PKO priority
    - Pomace must be at least 10% of total_qty
    - Ignores oils with CIF=0
    """

    oils = [
        {"name": "RBD", "cif": rbd_cif, "priority": 1},
        {"name": "Pomace", "cif": pomace_cif, "priority": 2},
        {"name": "Olive", "cif": olive_cif, "priority": 3},
        {"name": "PKO", "cif": pko_cif, "priority": 4}
    ]

    active_oils = [oil for oil in oils if oil["cif"] > 0]
    if not active_oils:
        return {"error": "No active oils with CIF > 0"}

    n = len(active_oils)

    # Constraints
    A_eq = [
        [1] * n,                             # total quantity
        [oil["cif"] for oil in active_oils] # total CIF
    ]
    b_eq = [total_qty, total_cif_budget]

    # Inequality: Pomace ≥ 10% of total_qty
    A_ub = []
    b_ub = []

    # Find Pomace index
    for i, oil in enumerate(active_oils):
        if oil["name"] == "Pomace":
            row = [0] * n
            row[i] = -1
            A_ub.append(row)
            b_ub.append(float(-0.10) * float(total_qty))
            break  # Only one constraint

    # Priority-based objective
    c = [-1000 / oil["priority"] for oil in active_oils]
    bounds = [(0, None)] * n

    result = linprog(c=c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub or None, b_ub=b_ub or None, bounds=bounds, method='highs')

    output = {}
    if result.success:
        quantities = result.x
        i = 0
        for oil in oils:
            if oil["cif"] == 0:
                output[f"{oil['name']} QTY"] = 0
                output[f"{oil['name']} CIF"] = 0
            else:
                qty = quantities[i]
                output[f"{oil['name']} QTY"] = round(qty, 2)
                output[f"{oil['name']} CIF"] = round(qty * oil["cif"], 2)
                i += 1
    else:
        output["error"] = "No feasible solution found."
        for oil in oils:
            output[f"{oil['name']} QTY"] = 0
            output[f"{oil['name']} CIF"] = 0

    output["Total Veg QTY"] = round(sum(output.get(f"{oil['name']} QTY", 0) for oil in oils), 2)
    output["Total CIF"] = round(sum(output.get(f"{oil['name']} CIF", 0) for oil in oils), 2)
    return output
