from docxtpl import DocxTemplate

import csv


def generate_documents():
    input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        print(context)
        doc = DocxTemplate("_consent_letter.docx")
        doc.render(context)
        doc.save(context['license'] + "_consent_letter.docx")
        doc = DocxTemplate("_request_letter.docx")
        doc.render(context)
        doc.save(context['license'] + "_request_letter.docx")


def fetch_cif():
    from license.models import LicenseDetailsModel
    licenses = LicenseDetailsModel.objects.all()
    for license in licenses:
        license.balance_cif = license.get_balance_cif()
        license.save()


def generate_tl():
    input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        print(context)
        doc = DocxTemplate("TL.docx")
        doc.render(context)
        doc.save(context['license'] + "_TL.docx")


def generate_agreement():
    input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        print(context)
        dict_data = context
        dict_data['today'] = dict_data['\ufefftoday']
        doc = DocxTemplate("Tri-party agreement.docx")
        doc.render(dict_data)
        doc.save(context['license'] + "_Tri-party agreement.docx")
