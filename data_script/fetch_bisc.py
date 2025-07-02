import csv
from django.db.models import Sum, Q
from core.management.commands.report_fetch import fetch_total, fetch_debited
from license.models import LicenseDetailsModel


def fetch_dfia_data(license_numbers):
    data_list = []

    for license_no in license_numbers:
        record = {"DFIA No": "'" + license_no}
        try:
            dfia = LicenseDetailsModel.objects.get(license_number=license_no)

            # General Info
            record.update({
                "DFIA Dt": dfia.license_date.strftime('%d/%m/%Y') if dfia.license_date else "",
                "DFIA Exp": dfia.license_expiry_date.strftime('%d/%m/%Y') if dfia.license_expiry_date else "",
                "Exporter": str(dfia.exporter) if dfia.exporter else "",
                "PORT": str(dfia.port) if dfia.port else "",
                "Ledger Date": dfia.ledger_date.strftime('%d/%m/%Y') if dfia.ledger_date else "",
                "Notf No": dfia.notification_number,
                "TOTAL CIF": float(dfia.opening_balance),
                "BAL CIF": float(dfia.get_balance_cif),
                "10% of CIF": int(dfia.opening_balance * 0.10),
                "10% of CIF Balance": dfia.get_per_cif(),
                "Is Individual": dfia.is_individual,
                "Is Conversion": ""
            })

            is_conversion = dfia.export_license.first().old_quantity != 0.0 if dfia.export_license.exists() else False
            if is_conversion or dfia.notification_number == "098/2009":
                record.update({
                    "10% of CIF Utilized": 0,
                    "10% of CIF Balance": 0,
                    "10% of CIF": 0,
                    "Is Conversion": True if is_conversion else ""
                })
            else:
                record["10% of CIF Utilized"] = int(dfia.opening_balance * 0.10) - record["10% of CIF Balance"]

            def add_item_data(label, queryset, old=False, used=False):
                if queryset.exists():
                    item = queryset.first()
                    record[f"HSN {label}"] = "'" + item.hs_code.hs_code
                    record[f"Total {label} Qty"] = queryset.aggregate(Sum("quantity"))["quantity__sum"]
                    record[f"BAL {label} QTY"] = fetch_total(queryset)
                    if old:
                        record[f"OLD {label} Qty"] = queryset.aggregate(Sum("old_quantity"))["old_quantity__sum"]
                    if used:
                        record[f"Utilized {label} Qty"] = fetch_debited(queryset)

            add_item_data("GLUTEN", dfia.import_license.filter(item__head__name__icontains="wheat"), old=True)
            add_item_data("RBD", dfia.import_license.filter(item__head__name__icontains="Palmolein"))
            add_item_data("DF", dfia.import_license.filter(item__head__name__icontains="dietary fibre"), old=True, used=True)
            add_item_data("FF", dfia.import_license.filter(item__head__name__icontains="food flavour"), old=True, used=True)
            add_item_data("FC", dfia.import_license.filter(item__head__name__icontains="fruit"), old=True, used=True)
            add_item_data("WPC", dfia.import_license.filter(hs_code__hs_code__icontains="3502"))
            add_item_data("SWP", dfia.import_license.filter(hs_code__hs_code__icontains="04041020").exclude(hs_code__hs_code__icontains="3502"))

            mm = dfia.import_license.filter(
                Q(item__head__name__icontains="milk") | Q(item__head__name__icontains="skimmed")
            ).exclude(
                Q(hs_code__hs_code__icontains="3502") | Q(hs_code__hs_code__icontains="04041020")
            )
            if mm.exists():
                record["Total M&M Oth QTY"] = mm.aggregate(Sum("quantity"))["quantity__sum"]
                record["BAL M&M Oth QTY"] = fetch_total(mm)

            starch = dfia.import_license.filter(description__icontains="starch")
            if starch.exists():
                record["Total Sugar QTY"] = starch.aggregate(Sum("quantity"))["quantity__sum"]
                record["BAL Sugar QTY"] = fetch_total(starch)

            leaven = dfia.import_license.filter(item__head__name__icontains="Leavening Agent")
            if leaven.exists():
                record["Total Leavening Agent QTY"] = leaven.aggregate(Sum("quantity"))["quantity__sum"]
                record["BAL Leavening Agent QTY"] = fetch_total(leaven)

            add_item_data("PP", dfia.import_license.filter(item__head__name__icontains="pp"))
            add_item_data("PAP", dfia.import_license.filter(item__head__name__icontains="paper & paper board"))

        except Exception as e:
            print(f"[ERROR] {license_no}: {e}")

        data_list.append(record)

    return data_list


def write_to_csv(data_list, file_path="bisc.csv"):
    if not data_list:
        print("No data to write.")
        return

    fieldnames = list(data_list[0].keys())

    with open(file_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data_list)

    print(f"✅ CSV written to {file_path}")


def get_license_list():
    license_numbers = """1310049708
0310838098
1310049730
1310049493
1310049731
1310049729
3010105354
0310831148
0310831149
0310831147
0310839564
0310837902
0310832494
0310838342
0310831880
0310834896
0310834967
0310831843
0310837998
0310831831
0310833305
0310833286
0310835514
0310835559
0310839189
0310832432
0310832433
0310832430
0310832398
0310833793
0310833141
0310833589
0310833591"""  # Truncated for brevity
    return license_numbers.split()


# Run script
if __name__ == "__main__":
    licenses = get_license_list()
    dfia_data = fetch_dfia_data(licenses)
    write_to_csv(dfia_data)
