# src/resume/profile.py
import re
from typing import List, Dict

DEFAULT_SKILLS = [
    "python","java","c++","go","rust","sql","docker","kubernetes",
    "aws","gcp","azure","pytorch","tensorflow","react","nodejs","fastapi",
    "flask","django","graphql","rest"
]

def normalize_text(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip().lower())

def extract_skills(text: str, skills_list=DEFAULT_SKILLS) -> List[str]:
    t = normalize_text(text)
    found = []
    for skill in skills_list:
        if re.search(r'\b' + re.escape(skill) + r'\b', t):
            found.append(skill)
    return found

def build_profile_from_text(text: str) -> Dict:
    skills = extract_skills(text)
    exp = None
    m = re.search(r'(\d+)\+?\s+years?', text.lower())
    if m:
        exp = int(m.group(1))
    # simple title extraction (first big line that looks like a title)
    title_match = None
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines:
        title_match = lines[0]
    return {
        "raw": text,
        "skills": skills,
        "years_experience": exp,
        "title_guess": title_match
    }
