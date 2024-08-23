import shutil



import csv

from docxtpl import DocxTemplate


def remove(path):
    """ param <path> could either be relative or absolute. """
    import os
    if os.path.isfile(path):
        os.remove(path)  # remove the file
    elif os.path.isdir(path):
        if os.path.exists(path) and os.path.isdir(path):
            shutil.rmtree(path)  # remove dir and all contains
    else:
        return True


def generate_documents(data=None, path=''):
    if data:
        input_file = data
        import os
        remove(path)
        os.mkdir(path)
    else:
        input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        doc = DocxTemplate("_consent_letter.docx")
        doc.render(context)
        doc.save(path + context['license'] + "_consent_letter.docx")
        doc = DocxTemplate("_request_letter.docx")
        doc.render(context)
        doc.save(path + context['license'] + "_request_letter.docx")


def fetch_cif():
    from license.models import LicenseDetailsModel
    licenses = LicenseDetailsModel.objects.all()
    for license in licenses:
        license.balance_cif = license.get_balance_cif
        license.save()


def generate_tl():
    input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        print(context)
        if context['tl_company'] == 'GE':
            doc = DocxTemplate("__GE_TL.docx")
            doc.render(context)
            doc.save(context['sr_no'] + ' ' + context['license'] + "_GE_TL.docx")
        if context['tl_company'] == 'gmpl':
            doc = DocxTemplate("__GMPL_TL.docx")
            doc.render(context)
            doc.save(context['sr_no'] + ' ' + context['license'] + "_GMPL_TL.docx")
        else:
            doc = DocxTemplate("__GE_TL.docx")
            doc.render(context)
            doc.save(context['sr_no'] + ' ' + context['license'] + "_GE_TL.docx")
            doc = DocxTemplate("__GMPL_TL.docx")
            doc.render(context)
            doc.save(context['sr_no'] + ' ' + context['license'] + "_GMPL_TL.docx")


def generate_agreement():
    input_file = csv.DictReader(open("aro_invalidation.csv", 'r', encoding='utf-8'))
    for context in input_file:
        print(context)
        dict_data = context
        doc = DocxTemplate("Tri-party agreement.docx")
        doc.render(dict_data)
        doc.save(context['license'] + "_Tri-party agreement.docx")


def generate_tl_software(data, tl_path, path='', transfer_letter_name=""):
    if data:
        input_file = data
        import os
        remove(path)
        os.mkdir(path)
        for context in data:
            doc = DocxTemplate(tl_path)
            doc.render(context)
            if len(str(context['license'])) == 9:
                context['license'] = '0' + str(data['license'])
            try:
                id = context['id']
                context['file_number'] = ''
                doc.save(path + context['license'] + '_' + transfer_letter_name + '_' + str(id) + "_TL.docx")
            except:
                doc.save(path + context['license'] + '_' + transfer_letter_name + "_TL.docx")


def generate_sugar():
    input_file = csv.DictReader(open("aro_details.csv"))
    for context in input_file:
        doc = DocxTemplate("SUGAR.docx")
        doc.render(context)
        doc.save(context['sr_no'] + ' ' + context['license'] + "_SUGAR.docx")
        doc = DocxTemplate("KS.docx")
        doc.render(context)
        doc.save(context['sr_no'] + ' ' + context['license'] + "_KS.docx")
