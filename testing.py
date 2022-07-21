from docxtpl import DocxTemplate
import csv
from docx2pdf import convert

with open('QUOTES.csv', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        print(row)
        doc = DocxTemplate("LOVE QUOTES.docx")
        context = {'QUOTES': row['\ufeffname']}
        doc.render(context)
        print(context)
        file_name = 'QUOTES/' + row['\ufeffname'].replace(' ', '_').replace('/', '_') + '.docx'
        doc.save(file_name)
    convert("QUOTES/")
    # convert(file_name, file_name.replace('.docx','.pdf'))
