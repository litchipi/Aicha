from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextLine
from io import StringIO

def load_pdf_file(f, sz):
    texts = list()

    output_string = StringIO()

    rsrcmgr = PDFResourceManager()
    device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    npage = 1
    with open(f, "rb") as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        pages = PDFPage.create_pages(doc)
        while True:
            try:
                page = next(pages)
            except StopIteration:
                break
            except Exception as err:
                print("Failed to load page from PDF: skipping the document")
                print("Error", err)
                break

            try:
                interpreter.process_page(page)
            except:
                print("Failed to process page: skipping the page")
                continue


            text = output_string.getvalue().replace("   ", " ").replace("  ", " ").strip()
            output_string.truncate(0)
            output_string.seek(0)

            if len(text) == 0:
                continue

            texts.append(text)

            text = " ".join(texts).strip()
            while len(text) > sz:
                last_space = text[:sz].rfind(" ")
                got = text[:last_space].strip()
                rest = text[last_space:].strip()

                texts = []
                if len(rest) > 0:
                    texts.append(rest)

                yield (f"page {npage}", got)
                npage += 1
                text = " ".join(texts).strip()
        yield (f"page {npage}", " ".join(texts).strip())
