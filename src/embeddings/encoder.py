# src/embeddings/encoder.py
from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = "all-MiniLM-L6-v2"

class Encoder:
    def __init__(self, model_name=MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        vecs = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return vecs
