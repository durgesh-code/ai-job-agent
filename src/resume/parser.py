# src/resume/parser.py
import os
from pdfminer.high_level import extract_text
from docx import Document

def extract_text_from_pdf(path: str) -> str:
    return extract_text(path)

def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    full = [p.text for p in doc.paragraphs]
    return "\n".join(full)

def extract_text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(path)
    else:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
