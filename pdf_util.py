from PyPDF2 import PdfReader

reader = PdfReader("file.pdf")
for outline in reader.outline:
    if isinstance(outline, list): continue
    page = reader.get_page(outline.page)  # 获取该目录项对应页码
    text = page.extract_text()