from decimal import Decimal


def optimize_product_usage(total_quantity, total_value):
    total_quantity = Decimal(total_quantity)
    total_value = Decimal(total_value)
    quantity1 = Decimal(0)
    unit_value1 = Decimal(1)

    total_unit_value = Decimal(total_value / total_quantity)
    if total_unit_value < 8:
        unit_value2 = Decimal(8)
    elif 8 <= total_unit_value < 9:
        unit_value2 = Decimal(9)
    else:
        unit_value2 = total_unit_value

    quantity2 = total_quantity  # Assign entire quantity to veg oil

    # Calculate values
    value1 = quantity1 * unit_value1
    value2 = round(quantity2 * unit_value2, 2)
    total_value_1_2 = value1 + value2

    if total_value_1_2 > total_value:
        balance = 0
        value2 = total_value
    else:
        balance = total_value - total_value_1_2

    unit_value2 = round(value2 / quantity2, 2)

    return {
        "pko": {"quantity": quantity1, "unit_value": unit_value1, "value": value1},
        "veg_oil": {"quantity": quantity2, "unit_value": unit_value2, "value": value2},
        "balance": balance
    }
