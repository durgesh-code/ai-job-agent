# src/api.py
from fastapi import FastAPI, UploadFile, File, Form
from .db import init_db
from .resume.parser import extract_text_from_file
from .resume.profile import build_profile_from_text
from .matcher.matcher import embed_and_store_jobs, match_profile

app = FastAPI(title="AI Job Agent")

@app.on_event("startup")
def startup():
    init_db()

@app.post("/upload_resume/")
async def upload_resume(file: UploadFile = File(...)):
    contents = await file.read()
    tmp_path = f"./data/{file.filename}"
    with open(tmp_path, "wb") as f:
        f.write(contents)
    txt = extract_text_from_file(tmp_path)
    profile = build_profile_from_text(txt)
    return {"profile": profile}

@app.post("/reindex_jobs/")
def reindex_jobs():
    embed_and_store_jobs()
    return {"status": "ok"}

@app.post("/match/")
def match(profile_text: str = Form(...), top_k: int = Form(10)):
    profile = build_profile_from_text(profile_text)
    matches = match_profile(profile, top_k=top_k)
    return {"matches": matches}
