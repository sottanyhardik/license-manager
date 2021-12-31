from reportlab.pdfgen import canvas
from PyPDF2 import PdfFileWriter, PdfFileReader
import glob

report_list =glob.glob("Reports/*")
image_list =glob.glob("IMG/*")


for image in image_list:
    out_image = image.split('/')[-1].replace('.png','.pdf')
    c = canvas.Canvas(out_image)
    c.drawImage(image,160,100,40,40)
    c.save()


for report in report_list:
    watermark_name = report.split('/')[-1].split('(')[0] + '.pdf'
    watermark = PdfFileReader(open(watermark_name, "rb"))
    output_file = PdfFileWriter()
    input_file = PdfFileReader(open(report, "rb"))
    input_page = input_file.getPage(0)
    input_page.mergePage(watermark.getPage(0))
    output_file.addPage(input_page)
    out_file_name = report.replace('Reports','NR')
    with open(out_file_name, "wb") as outputStream:
        output_file.write(outputStream)