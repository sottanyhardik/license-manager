from docxtpl import DocxTemplate

import csv


def generate_documents(path=''):
    input_file = csv.DictReader(open("license_details.csv"))
    for context in input_file:
        doc = DocxTemplate("consent_letter.docx")
        doc.render(context)
        doc.save(path + context['license_number'] + "_consent_letter.docx")
        doc = DocxTemplate("aro_request_letter.docx")
        doc.render(context)
        doc.save(path + context['license_number'] + "_request_letter.docx")


def generate_tl():
    input_file = csv.DictReader(open("aro_license.csv"))
    for context in input_file:
        doc = DocxTemplate("gmpl_tl.docx")
        doc.render(context)
        doc.save(context['license_no'] + "_gmpl_tl.docx")
        doc = DocxTemplate("ge_tl.docx")
        doc.render(context)
        doc.save(context['license_no'] + "_ge_tl.docx")