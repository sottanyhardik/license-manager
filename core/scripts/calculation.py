def split_vegetable_oil_quantity(total_quantity, total_value):
    # Set default values
    quantity1 = total_quantity
    unit_value1 = 1
    quantity2 = 0
    unit_value2 = 0
    # Adjust values if total_value is greater than or equal total_quantity
    if total_value >= total_quantity:
        quantity2 = (total_value - total_quantity) // 8
        quantity1 = total_quantity - quantity2
        unit_value2 = 8 if quantity2 else 0
    balance = total_value - (quantity1 * unit_value1 + quantity2 * unit_value2)
    return [(quantity1, unit_value1), (quantity2, unit_value2), balance]
