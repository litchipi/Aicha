import os
import sys
import gzip
import json
import time
from nomic import embed
from sklearn.metrics.pairwise import euclidean_distances
import numpy as np
import hashlib

from io import StringIO

from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextLine

import pickle

def save_data(data, fpath):
    with gzip.open(fpath, "wb") as f:
        pickle.dump(data, f)

def load_data(fpath):
    with gzip.open(fpath, "rb") as f:
        return pickle.load(file)

def compute_file_hash(fpath):
    with open(fpath, "rb") as f:
        hasher = hashlib.sha256()
        while True:
            data = f.read(1 << 22)
            if len(data) == 0:
                break

            hasher.update(data)
        return hasher.hexdigest()

def get_embeddings(*data):
    return embed.text(
        list(data),
        inference_mode="local",
        model="nomic-embed-text-v1.5",
        model_path=".model",
    )['embeddings']

# TODO    Do not break in the middle of a word
def load_text_file(f, sz):
    with open(f, "r") as f:
        while True:
            data = f.read(sz)
            if not data:
                break
            yield data

def load_pdf_file(f, sz):
    texts = list()

    output_string = StringIO()

    rsrcmgr = PDFResourceManager()
    device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    with open(f, "rb") as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)

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

                yield got
                text = " ".join(texts).strip()
        yield " ".join(texts).strip()

# File handlers, should sanitize their output as well
# TODO    Handle for "epub"
FILETYPE_HANDLERS = {
    "txt": load_text_file,
    "md": load_text_file,
    "xml": load_text_file,
    "pdf": load_pdf_file,
}

class KnowledgeLibrary:
    def __init__(self, db_dir, dirpath):
        ## Saved to db_file
        self.chunk_size = 512
        self.database = dict()
        ###

        self.db_dir = os.path.abspath(db_dir)
        self.cache_dir = os.path.join(self.db_dir, "cache")
        self.data_dir = dirpath
        os.makedirs(self.db_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        db_file = os.path.join(self.db_dir, "database.gz")
        if os.path.isfile(db_file):
            print(f"[*] Loading database from file {db_file}")
            data = load_data(db_file)
            self.database = data["database"]
            self.chunk_size = data["chunk_size"]

        print(f"[*] Building database from directory {dirpath}")
        self.build_db(dirpath)

        print(f"[*] Saving database to file {db_file}")
        save_data({
            "database": self.database,
            "chunk_size": self.chunk_size,
        }, db_file)

    def compute_dirpath_hash(self, dirpath):
        hasher = hashlib.sha256()
        for (root, _, files) in os.walk(dirpath):
            for f in files:
                hasher.update(os.path.relpath(self.db_dir, os.path.join(root, f)).encode())
        return hasher.digest().hex()

    # TODO    Have this paralellized
    def build_db(self, dirpath):
        for (root, _, files) in os.walk(dirpath):
            for f in files:
                if not self.readable_file(f):
                    continue

                fpath = os.path.join(root, f)
                self.add_file_to_db(os.path.join(root, f))

    def readable_file(self, fpath):
        return ("." in fpath) and (fpath.split(".")[-1] in FILETYPE_HANDLERS.keys())

    # TODO    Get the size of the file, then display a progress bar
    #    based on the number of chunks x chunk_size (will not be correct but still)
    def add_file_to_db(self, fpath, max_chunks_process=80):
        nchunks = 0
        chunks = list()
        generator = FILETYPE_HANDLERS[fpath.split(".")[-1]](fpath, self.chunk_size)

        dbkey = os.path.relpath(fpath, self.data_dir)
        file_hash = compute_file_hash(fpath)

        if (dbkey in self.database) and (self.database[dbkey]["file_hash"] == file_hash):
            return

        self.database[dbkey] = {
            "file_hash": file_hash,
            "vectors": list(),
            "index": list(),
        }

        cache_data = {
            "file_hash": file_hash,
            "nb_chunks": 0,
            "vectors": list(),
            "index": list(),
            "path": fpath,
        }

        cache_file = os.path.join(self.db_dir, "cache", cache_data["file_hash"] + ".gz")
        if os.path.isfile(cache_file):
            data = load_data(cache_file)
            if "database" in data.keys():
                data["vectors"] = data["database"]
                del data["database"]
                save_data(data, cache_file)

            if data["file_hash"] == cache_data["file_hash"]:
                cache_fname = os.path.relpath(cache_file, self.cache_dir)
                print(f" - Loading file {fpath} from cache file {cache_fname}")
                for (n, d) in enumerate(data["vectors"]):
                    self.database[dbkey]["vectors"].append(d)
                    # TODO    Get a refernence (line, page, etc... from extractor)
                    # self.database[dbkey]["index"].append(n)
                return

        print(f" - Processing file {fpath}")
        while True:
            try:
                chunk = next(generator)
            except StopIteration:
                break

            if len(chunk) == 0:
                continue

            chunks.append(chunk.lower())
            if len(chunks) >= max_chunks_process:
                for (n, data) in enumerate(get_embeddings(*chunks)):
                    self.database[dbkey]["vectors"].append(data)
                    cache_data["vectors"].append(data)
                    # TODO    Get a refernence (line, page, etc... from extractor)
                    # self.database[dbkey]["index"].append(n)

                nchunks += len(chunks)
                chunks = list()
        cache_data["nb_chunks"] = nchunks

        save_data(cache_data, cache_file)

    def query_db(self, query, nmax=10, threshold=0.9):
        if len(self.database) == 0:
            return []

        db_keys = sorted(self.database.keys())
        all_vectors = []
        all_indexes = []
        for key in db_keys:
            for (n, vec) in enumerate(self.database[key]["vectors"]):
                all_vectors.append(vec)
                all_indexes.append((key, n))

        query_vector = get_embeddings(query)
        distances = sorted([
            (n, dist)
            for (n, dist) in enumerate(euclidean_distances(query_vector, all_vectors)[0])
            if (dist < threshold)
        ], key = lambda x: x[1])

        bestmatch = [n for (n, _) in distances[:nmax]]
        print(bestmatch)

        fnames = [all_indexes[i] for i in bestmatch]
        print(", ".join([f"{f}:{l}" for (f, l) in fnames]))

        toget = dict()
        for (f, n) in fnames:
            if f in toget:
                toget[f].append(n)
            else:
                toget[f] = [ n ]

        chunks = list()
        for (relf, nlist) in toget.items():
            f = os.path.join(self.data_dir, f)
            for (nc, chunk) in enumerate(FILETYPE_HANDLERS[f.split(".")[-1]](f, self.chunk_size)):
                if nc in nlist:
                    chunks.append(chunk)

        return chunks

if __name__ == "__main__":
    library = KnowledgeLibrary(".rag", ".rag/data") # TODO    Get from sys.argv

    print("Question 1:")
    got = library.query_db("Explain me the different AI algorithms that can be used for natural language processing (NLP)")
    for chunk in got:
        print(chunk)
    input("")

    print("Question 2:")
    got = library.query_db("Tell me about the RSA algorithm, how it works, and its advantages")
    for chunk in got:
        print(chunk)
    input("")
