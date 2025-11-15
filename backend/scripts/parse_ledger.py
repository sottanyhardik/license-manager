import datetime


def parse_date(date_str):
    from datetime import datetime
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return None


def parse_license_data(rows):
    """
    Parses a list of rows (from CSV or OCR extraction) into structured dict_list based on license groupings.
    Each new 'Regn.No' row marks the beginning of a new license section.
    """
    dict_list = []
    current = None

    for row in rows:
        # Skip completely empty rows
        if not any(cell.strip() for cell in row):
            continue

        if len(row) < 2:
            continue

        # Detect start of new license block
        if row[0] == "Regn.No.":
            if current:
                dict_list.append(current)
            if len(row[5]) == 9:
                row[5] = "0" + row[5]
            current = {
                "ledger_date": datetime.datetime.now().date(),
                "registration_no": row[1],
                "registration_date": row[3],
                "lic_no": row[5],
                "lic_date": row[7],
                "row": []
            }
        elif row[0] == "RANo.":
            current["port"] = row[5]
        elif row[0] == "IEC":
            if len(row[1]) == 9:
                row[1] = "0" + row[1]
            current["iec"] = row[1]
            current["scheme_code"] = row[3]
            current["notification"] = row[5]
            current["foregin_currency"] = row[7]

        elif row[0].lower() == "tot.duty":
            current["cif_inr"] = float(row[3]) if row[3] else 0
            current["total_quantity"] = float(row[5]) if row[5] else 0
            current["cif_fc"] = float(row[7]) if row[7] else 0

        elif row[0] and row[0].lower() in ["credit-", "debit-"]:
            if row[0].lower() == 'credit-':
                txn = {
                    "type": 'C',
                    "sr_no": int(row[1]) if row[1] else None,
                    "cif_inr": float(row[3]) if row[3] else 0,
                    "cif_fc": float(row[4]) if row[4] else 0,
                    "qty": float(row[5]) if row[5] else 0,
                    "be_number": row[7] if len(row) > 5 else None,
                    "be_date": row[8] if len(row) > 6 else None,
                    "port": row[9] if len(row) > 7 else None
                }

            else:
                txn = {
                    "type": 'D',
                    "sr_no": int(row[1]) if row[1] else None,
                    "cif_inr": float(row[3]) if row[3] else 0,
                    "cif_fc": float(row[4]) if row[4] else 0,
                    "qty": float(row[5]) if row[5] else 0,
                    "be_number": row[7] if len(row) > 5 else None,
                    "be_date": parse_date(row[8]) if len(row) > 8 else None,
                    "port": row[9] if len(row) > 7 else None
                }
            current["row"].append(txn)

    if current:
        dict_list.append(current)

    return dict_list
