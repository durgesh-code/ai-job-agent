# src/crawler/vendors.py
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import hashlib

def greenhouse_list_jobs(url):
    """
    If url points to Greenhouse company board (e.g. https://boards.greenhouse.io/company),
    Greenhouse provides JSON via appended '/jobs' pages or structured HTML.
    We'll attempt to fetch the board and parse job links.
    """
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for a in soup.select("a[href]"):
        t = (a.get_text() or "").strip()
        href = a["href"]
        if not t: continue
        if re.search(r"\b(engineer|developer|backend|frontend|software|full[\s-]?stack|ml)\b", t, re.I):
            job_url = href if href.startswith("http") else urljoin(url, href)
            print(f"Found job at {job_url}")
            # fetch job page
            try:
                jr = requests.get(job_url, timeout=12)
                jr.raise_for_status()
                desc = BeautifulSoup(jr.text, "html.parser").get_text(separator="\n")
                h = hashlib.sha256(desc.encode("utf-8")).hexdigest()
                jobs.append({
                    "external_id": h[:12],
                    "title": t,
                    "description": desc,
                    "apply_url": job_url,
                    "raw_hash": h
                })
            except Exception:
                continue
    return jobs

def lever_list_jobs(url):
    """
    For Lever: many companies host jobs under jobs.lever.co/<company>.
    Lever also has JSON endpoints for job listings; but we parse HTML fallback.
    """
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    jobs = []
    for a in soup.select("a[href]"):
        t = (a.get_text() or "").strip()
        href = a["href"]
        if not t: continue
        if re.search(r"\b(engineer|developer|backend|frontend|software|full[\s-]?stack|ml)\b", t, re.I):
            job_url = href if href.startswith("http") else urljoin(url, href)
            try:
                jr = requests.get(job_url, timeout=12)
                jr.raise_for_status()
                desc = BeautifulSoup(jr.text, "html.parser").get_text(separator="\n")
                h = hashlib.sha256(desc.encode("utf-8")).hexdigest()
                jobs.append({
                    "external_id": h[:12],
                    "title": t,
                    "description": desc,
                    "apply_url": job_url,
                    "raw_hash": h
                })
            except Exception:
                continue
    return jobs
