# src/main.py
import asyncio
import sys
from .db import init_db
from .crawler.company_finder import discover_and_store_companies
from .crawler.scraper import crawl_all_companies
from .resume.parser import extract_text_from_file
from .resume.profile import build_profile_from_text
from .matcher.matcher import embed_and_store_jobs, match_profile

async def run_pipeline(resume_path: str, location: str):
    init_db()
    print(f"Discovering companies in {location} ...")
    try:
        added = discover_and_store_companies(location, comprehensive=True, max_per_category=15)
        print(f"Discovered and stored {added} companies (careers url may be missing for some).")
    except Exception as e:
        print("Company discovery failed:", e)
        raise e
    print("Crawling company career pages...")
    added_jobs = await crawl_all_companies()
    print(f"Added {added_jobs} new jobs.")
    print("Indexing jobs (embeddings)...")
    embed_and_store_jobs()
    print("Parsing resume...")
    txt = extract_text_from_file(resume_path)
    profile = build_profile_from_text(txt)
    print("Matching profile to jobs...")
    matches = match_profile(profile, top_k=20)
    print("Top matches:")
    for m in matches[:20]:
        print(f"{m['title']} — {m['apply_url']} (score: {m['score']:.3f})")
    # optionally: send email via notifier if set up
    return matches

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m src.main <resume_path> <location>")
        sys.exit(1)
    resume = sys.argv[1]
    print(f"Using resume: {resume}")
    location = sys.argv[2]
    print(f"Using location: {location}")
    asyncio.run(run_pipeline(resume, location))
