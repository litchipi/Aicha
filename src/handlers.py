import pdf

def read_text_chunks_from(fpath, chunk_size):
    return FILETYPE_HANDLERS[fpath.split(".")[-1]](fpath, chunk_size)

def readable_file(fpath):
    return ("." in fpath) and (fpath.split(".")[-1] in FILETYPE_HANDLERS.keys())

# TODO    Do not break in the middle of a word
def load_text_file(f, sz):
    nline = 1
    with open(f, "r") as f:
        while True:
            data = f.read(sz)
            if not data:
                break
            nline += data.count("\n")
            yield (f"line {nline}", data)

# File handlers, should sanitize their output as well
# TODO    Handle for "epub"
FILETYPE_HANDLERS = {
    "txt": load_text_file,
    "md": load_text_file,
    "xml": load_text_file,
    "pdf": pdf.load_pdf_file,
}
