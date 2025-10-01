# src/matcher/matcher.py
from ..embeddings.encoder import Encoder
from ..embeddings.vector_store import FaissStore
from ..db import SessionLocal
from ..models import Job
import numpy as np

encoder = Encoder()
VECTOR_DIM = 384  # all-MiniLM-L6-v2 dim
vs = FaissStore(d=VECTOR_DIM)

def embed_and_store_jobs():
    db = SessionLocal()
    jobs = db.query(Job).all()
    texts = []
    ids = []
    for j in jobs:
        text = (j.title or "") + "\n" + (j.description or "")
        texts.append(text)
        ids.append(f"job:{j.id}")
    if texts:
        vecs = encoder.encode(texts)
        vs.add(vecs, ids)
    db.close()

def match_profile(profile: dict, top_k: int = 10):
    vec = encoder.encode(profile["raw"])[0]
    results = vs.search(vec, top_k=top_k)[0]
    matches = []
    db = SessionLocal()
    for r in results:
        if "id" not in r:
            continue
        job_id = int(r["id"].split(":")[1])
        job = db.query(Job).filter(Job.id==job_id).first()
        if not job:
            continue
        skill_overlap = 0
        reasons = []
        job_text = (job.title or "") + " " + (job.description or "")
        for s in profile.get("skills", []):
            if s.lower() in job_text.lower():
                skill_overlap += 1
                reasons.append(s)
        semantic_score = r["score"]
        if profile.get("skills"):
            overlap_score = min(1.0, skill_overlap / max(1, len(profile["skills"])))
        else:
            overlap_score = 0.0
        final_score = 0.7 * semantic_score + 0.3 * overlap_score
        matches.append({
            "job_id": job.id,
            "company_id": job.company_id,
            "title": job.title,
            "location": job.location,
            "apply_url": job.apply_url,
            "score": float(final_score),
            "semantic_score": float(semantic_score),
            "skill_overlap": skill_overlap,
            "reasons": reasons
        })
    db.close()
    matches = sorted(matches, key=lambda x: x["score"], reverse=True)
    return matches
