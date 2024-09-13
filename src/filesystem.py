import os
import gzip
import pickle
import hashlib

def save_data(data, fpath):
    with gzip.open(fpath, "wb") as f:
        pickle.dump(data, f)

def load_data(fpath):
    with gzip.open(fpath, "rb") as f:
        return pickle.load(f)

def ensure_path_exist(d):
    if (not os.path.isdir(d)) and (not os.path.islink(d)):
        os.makedirs(d)

def compute_file_hash(fpath):
    with open(fpath, "rb") as f:
        hasher = hashlib.sha256()
        while True:
            data = f.read(1 << 22)
            if len(data) == 0:
                break

            hasher.update(data)
        return hasher.hexdigest()
