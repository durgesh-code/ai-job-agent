# src/embeddings/vector_store.py
import faiss
import numpy as np
import os
import pickle

class FaissStore:
    def __init__(self, d: int, path="./data/embeddings.faiss", id_path="./data/ids.pkl"):
        self.path = path
        self.id_path = id_path
        self.d = d
        self.index = None
        self.ids = []
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.exists(id_path):
            try:
                self.index = faiss.read_index(path)
                with open(self.id_path, "rb") as f:
                    self.ids = pickle.load(f)
            except Exception:
                self.index = faiss.IndexFlatIP(d)
                self.ids = []
        else:
            self.index = faiss.IndexFlatIP(d)
            self.ids = []

    def add(self, vecs: np.ndarray, ids: list):
        if vecs.ndim == 1:
            vecs = vecs.reshape(1, -1)
        self.index.add(vecs)
        self.ids.extend(ids)
        self._save()

    def search(self, vec: np.ndarray, top_k=10):
        if vec.ndim == 1:
            vec = vec.reshape(1, -1)
        if self.index.ntotal == 0:
            return [[]]
        D, I = self.index.search(vec, top_k)
        results = []
        for dist_row, idx_row in zip(D, I):
            row = []
            for dist, idx in zip(dist_row, idx_row):
                if idx < 0 or idx >= len(self.ids): continue
                row.append({"id": self.ids[idx], "score": float(dist)})
            results.append(row)
        return results

    def _save(self):
        faiss.write_index(self.index, self.path)
        with open(self.id_path, "wb") as f:
            pickle.dump(self.ids, f)
