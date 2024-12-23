import os
from pdf2docx import Converter

# Folder containing the PDF files
folder_path = "my_docx_folder"

# Create a function to convert PDF to DOCX
def convert_pdfs_in_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"Folder '{folder_path}' does not exist.")
        return
    # Get all PDF files in the folder
    pdf_files = [file for file in os.listdir(folder_path) if file.endswith('.pdf')]
    if not pdf_files:
        print(f"No PDF files found in the folder '{folder_path}'.")
        return
    # Convert each PDF file to DOCX
    for pdf_file in pdf_files:
        pdf_path = os.path.join(folder_path, pdf_file)
        docx_file = pdf_file.replace('.pdf', '.docx')
        docx_path = os.path.join(folder_path, docx_file)
        print(f"Converting {pdf_file} to {docx_file}...")
        # Perform the conversion
        cv = Converter(pdf_path)
        cv.convert(docx_path)
        cv.close()
        print(f"Converted: {docx_path}")

# Run the function
convert_pdfs_in_folder(folder_path)
from docx2pdf import convert
convert("my_docx_folder/")
