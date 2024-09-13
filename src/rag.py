import os
import hashlib
from gpt4all import Embed4All
from sklearn.metrics.pairwise import euclidean_distances

from filesystem import save_data, load_data, ensure_path_exist, compute_file_hash
from handlers import read_text_chunks_from, readable_file
from interface import msg_system

CHUNK_SIZE=512

class KnowledgeLibrary:
    def __init__(self,
             cache_dir,
             dirpath,
             model_dir,
             njobs=1,
             fpath_filter="",
             do_not_build=False,
         ):

        self.fpath_filter = fpath_filter.lower()
        self.knowledge = dict()
        self.do_not_build=do_not_build

        self.cache_dir = os.path.abspath(cache_dir)
        self.data_dir = dirpath
        ensure_path_exist(self.cache_dir)
        ensure_path_exist(model_dir)

        self.embed4all = Embed4All(
            # device="nvidia",
            model_name="nomic-embed-text-v1.5.f16.gguf",
            model_path=model_dir,
            n_threads=njobs,
        )

        msg_system(f"[*] Building knowledge from directory {dirpath}")
        self.build_db(dirpath)

    def compute_dirpath_hash(self, dirpath):
        hasher = hashlib.sha256()
        for (root, _, files) in os.walk(dirpath):
            for f in files:
                hasher.update(os.path.relpath(self.data_dir, os.path.join(root, f)).encode())
        return hasher.digest().hex()

    def build_db(self, dirpath):
        nb_files = 0
        for (root, _, files) in os.walk(dirpath):
            for f in files:
                if self.fpath_filter not in f.lower():
                    continue

                if not readable_file(f):
                    continue

                # Data added to knowledge
                if self.add_file_to_db(os.path.join(root, f)):
                    nb_files += 1
        if nb_files == 0:
            msg_system("Warning: No files were found in", dirpath, "the knowledge is empty")

    def add_file_to_db(self, fpath, max_chunks_process=20):
        dbkey = os.path.relpath(fpath, self.data_dir)
        file_hash = compute_file_hash(fpath)

        # If we have a double in the documents
        if (dbkey in self.knowledge) and (self.knowledge[dbkey]["file_hash"] == file_hash):
            return False

        self.knowledge[dbkey] = {
            "file_hash": file_hash,
            "vectors": list(),
            "index": list(),
        }

        # Attempt to read the cache data for this file
        cache_file = os.path.join(self.cache_dir, file_hash + ".gz")
        if os.path.isfile(cache_file):
            cache_data = load_data(cache_file)

            if cache_data["file_hash"] == file_hash:
                cache_fname = os.path.relpath(cache_file, self.cache_dir)
                msg_system(f" - Loading file {dbkey} from cache file {cache_fname}")
                for (n, chunk) in enumerate(cache_data["vectors"]):
                    self.knowledge[dbkey]["vectors"].append(chunk)
                    self.knowledge[dbkey]["index"].append(cache_data["index"][n])
                return True

        # If cache file doesn't exist, and we don't want to process the file now
        elif self.do_not_build:
            return False

        cache_data = {
            "file_hash": file_hash,
            "vectors": list(),
            "index": list(),
            "path": dbkey,
        }

        msg_system(f" - Processing file {dbkey}")
        chunks = list()
        refs = list()
        generator = read_text_chunks_from(fpath, CHUNK_SIZE)
        while True:
            (ref, chunk) = next(generator)

            if len(chunk) == 0:
                continue

            refs.append(ref)
            chunks.append(chunk.lower())
            if len(chunks) >= max_chunks_process:
                for (n, data) in enumerate(self.embed4all.embed(chunks)):
                    self.knowledge[dbkey]["vectors"].append(data)
                    cache_data["vectors"].append(data)

                    self.knowledge[dbkey]["index"].append(refs[n])
                    cache_data["index"].append(ref)
                chunks = list()
                refs = list()

        save_data(cache_data, cache_file)
        return True

    def query_db(self, query, nmax=10, threshold=0.9):
        if len(self.knowledge) == 0:
            return []

        db_keys = sorted(self.knowledge.keys())
        all_vectors = []
        all_indexes = []
        for key in db_keys:
            for (n, vec) in enumerate(self.knowledge[key]["vectors"]):
                all_vectors.append(vec)
                all_indexes.append((key, n))

        query_vector = self.embed4all.embed(query)
        distances = sorted([
            (n, dist)
            for (n, dist) in enumerate(euclidean_distances(query_vector, all_vectors)[0])
            if (dist < threshold)
        ], key = lambda x: x[1])

        bestmatch = [n for (n, _) in distances[:nmax]]

        fnames = [all_indexes[i] for i in bestmatch]

        toget = dict()
        for (f, n) in fnames:
            if f in toget:
                toget[f].append(n)
            else:
                toget[f] = [ n ]

        chunks = list()
        for (relf, nlist) in toget.items():
            f = os.path.join(self.data_dir, f)
            for (nc, chunk) in enumerate(read_text_chunks_from(f, CHUNK_SIZE)):
                if nc in nlist:
                    chunks.append(chunk)

        return chunks
