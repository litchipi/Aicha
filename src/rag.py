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
        if not do_not_build:
            self.analyse_data_directory(dirpath)

    def compute_dirpath_hash(self, dirpath):
        hasher = hashlib.sha256()
        for (root, _, files) in os.walk(dirpath):
            for f in files:
                hasher.update(os.path.relpath(self.data_dir, os.path.join(root, f)).encode())
        return hasher.digest().hex()

    def file_pass_filter(self, fpath):
        ok = self.fpath_filter in f.lower()
        ok = ok and readable_file(f)
        return ok

    def analyse_data_directory(self, dirpath):
        nb_files = 0

        for (root, _, files) in os.walk(dirpath):
            for f in files:
                fpath = os.path.join(root, f)
                if not self.file_pass_filter(fpath):
                    continue

                if self.analyse_file_to_cache(fpath):
                    nb_files += 1

        if nb_files == 0:
            msg_debug("No files were found in", dirpath, "no knowledge is loaded")

    def analyse_file_to_cache(self, fpath, max_chunks_process=20):
        dbkey = os.path.relpath(fpath, self.data_dir)
        file_hash = compute_file_hash(fpath)

        # Attempt to read the cache data for this file
        cache_file = os.path.join(self.cache_dir, file_hash + ".gz")
        if os.path.isfile(cache_file):
            cache_data = load_data(cache_file)

            if cache_data["file_hash"] == file_hash:
                return True

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
            try:
                (ref, chunk) = next(generator)
            except StopIteration:
                break

            if len(chunk) == 0:
                continue

            refs.append(ref)
            chunks.append(chunk.lower())
            if len(chunks) >= max_chunks_process:
                for (n, data) in enumerate(self.embed4all.embed(chunks)):
                    cache_data["vectors"].append(data)
                    cache_data["index"].append(ref)
                chunks = list()
                refs = list()

        save_data(cache_data, cache_file)
        return True

    def query_db(self, query, nmax=10, threshold=0.9):
        query_vector = self.embed4all.embed(query)

        matches = list()
        for (root, _, files) in os.walk(self.cache_dir):
            for f in files:
                if not self.file_pass_filter(f):
                    continue

                cache_data = load_data(f)
                fpath = os.path.join(self.data_dir, cache_data["path"])
                if not os.path.isfile(fpath):
                    msg_debug(f"File {fpath} not found anymore in knowledge base")
                    continue

                for (n, dist) in enumerate(euclidean_distances(query_vector, cache_data["vectors"])):
                    if dist < threshold:
                        matches.append((fpath, cache_data["index"][n], n, dist))

        if len(matches) == 0:
            msg_debug("No files matched the query, returning empty results")
            return []

        msg_debug("{} files matched the query".format(len(bestmatch)))
        bestmatch = sorted(matches, key=lambda x: x[3])[:nmax]

        toget = dict()
        for (path, _, n, _) in bestmatch:
            if path not in toget:
                toget[path] = [ n ]
            else:
                toget[path].append(n)

        chunks = list()
        for (fpath, nlist) in toget.items():
            for (nc, chunk) in enumerate(read_text_chunks_from(fpath, CHUNK_SIZE)):
                if nc in nlist:
                    yield chunk
        raise StopIteration
