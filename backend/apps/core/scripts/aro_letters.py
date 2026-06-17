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


def generate_documents_letters():
    path = 'AMENDMENT/'
    input_file = csv.DictReader(open("con_list.csv"))
    for context in input_file:
        doc = DocxTemplate("_sample_letter.docx")
        if len(context['license']) != 10:
            context['license'] = '0' + context['license']
            if not 'rama' in context['exporter'].lower() and not 'rani' in context[
                'exporter'].lower() and not 'parle' in context['exporter'].lower():
                context['exporter'] = 'JASH MERCANTILE PRIVATE LIMITED'
            elif 'parle' in context['exporter'].lower():
                context['exporter'] = 'PARLE PRODCUCTS PRIVATE LIMITED'
        doc.render(context)
        doc.save(path + context['license'] + "_letter.docx")
