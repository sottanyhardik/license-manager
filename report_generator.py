from docxtpl import DocxTemplate
import csv
from docx2pdf import convert

with open('Book14.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        doc = DocxTemplate("QR.docx")
        context = {'name': row['name'], 'patient_id': row['patient_id'], 'qr_id': row['qr_id'], 'time_1': row['time_1'],
                   'time_3': row['time_3'], 'time_2': row['time_2'], 'lab_address_1':row['lab_address_1'], 'lab_address_2':row['lab_address_2'],
                   'address_line_1':row['address_line_1'],'address_line_2':row['address_line_2']}
        doc.render(context)
        file_name = 'Qr/' + row['name'].replace(' ', '_').replace('/', '_') + '.docx'
        doc.save(file_name)
        # convert(file_name, file_name.replace('.docx', '.pdf'))
        doc = DocxTemplate("DOCUMENTS.docx")
        context = {'name': row['name'], 'patient_id': row['patient_id'], 'qr_id': row['qr_id'], 'time_1': row['time_1'],
                   'time_3': row['time_3'], 'time_2': row['time_2'], 'lab_address_1':row['lab_address_1'], 'lab_address_2':row['lab_address_2'],
                   'address_line_1':row['address_line_1'],'address_line_2':row['address_line_2']}
        doc.render(context)
        file_name = 'Reports/' + row['name'].replace(' ', '_').replace('/', '_') + '.docx'
        doc.save(file_name)
    convert("Reports/")
    convert("Qr/")
    # convert(file_name, file_name.replace('.docx','.pdf'))
