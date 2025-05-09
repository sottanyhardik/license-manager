from django.shortcuts import render, redirect
from .models import License, TradeParty, BuySellInvoice
from django.db.models import Sum
from django.http import HttpResponse
import csv

def index(request):
    licenses = License.objects.all()
    scheme_filter = request.GET.get('scheme')
    if scheme_filter:
        licenses = licenses.filter(scheme=scheme_filter)

    license_data = []
    for lic in licenses:
        purchases = BuySellInvoice.objects.filter(license=lic, is_purchase=True).aggregate(Sum('amount'))['amount__sum'] or 0
        sales = BuySellInvoice.objects.filter(license=lic, is_purchase=False).aggregate(Sum('amount'))['amount__sum'] or 0
        balance = purchases - sales
        license_data.append({
            'license': lic,
            'purchases': purchases,
            'sales': sales,
            'balance': balance
        })
    return render(request, 'other_script/index.html', {'license_data': license_data, 'schemes': License._meta.get_field('scheme').choices})

def add_license(request):
    if request.method == 'POST':
        License.objects.create(
            number=request.POST['number'],
            scheme=request.POST['scheme'],
            issue_date=request.POST['issue_date'],
            expiry_date=request.POST['expiry_date'],
            total_value=request.POST['total_value'],
            balance_value=request.POST['balance_value']
        )
        return redirect('/')
    return render(request, 'other_script/add_license.html')

def add_invoice(request):
    if request.method == 'POST':
        license = License.objects.get(id=request.POST['license'])
        party, _ = TradeParty.objects.get_or_create(name=request.POST['party'])
        license_value = float(request.POST['license_value'])
        rate = float(request.POST['rate'])
        amount = license_value * rate
        BuySellInvoice.objects.create(
            license=license,
            party=party,
            is_purchase=request.POST['type'] == 'purchase',
            invoice_number=request.POST['invoice_number'],
            invoice_date=request.POST['invoice_date'],
            license_value=license_value,
            rate=rate,
            amount=amount,
            remarks=request.POST['remarks']
        )
        return redirect('/')
    return render(request, 'other_script/add_invoice.html', {'licenses': License.objects.all()})

def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="license_report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Number', 'Scheme', 'Issue Date', 'Expiry Date', 'Total', 'Purchased', 'Sold', 'Balance'])
    for lic in License.objects.all():
        purchases = BuySellInvoice.objects.filter(license=lic, is_purchase=True).aggregate(Sum('amount'))['amount__sum'] or 0
        sales = BuySellInvoice.objects.filter(license=lic, is_purchase=False).aggregate(Sum('amount'))['amount__sum'] or 0
        writer.writerow([lic.number, lic.scheme, lic.issue_date, lic.expiry_date, lic.total_value, purchases, sales, purchases - sales])
    return response
