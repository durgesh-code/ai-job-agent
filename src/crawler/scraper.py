# src/crawler/scraper.py
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from ..db import SessionLocal
from ..models import Company, Job
from .vendors import greenhouse_list_jobs, lever_list_jobs
import hashlib
import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import aiohttp
import time
from datetime import datetime
from typing import List, Dict, Optional, Union
from threading import Lock
from sqlalchemy import text

ENGINEERING_KEYWORDS = [
    "software engineer", "backend engineer", "frontend engineer",
    "full stack", "full-stack", "developer", "ml engineer", "data engineer"
]

def looks_like_engineering(title: str, desc: str = "") -> bool:
    t = (title or "").lower()
    d = (desc or "").lower()
    if any(k in t for k in ENGINEERING_KEYWORDS):
        return True
    # fallback: search description
    if any(k in d for k in ["software engineer","backend","frontend","full stack","full-stack","developer","machine learning","ml engineer"]):
        return True
    return False

async def fetch_with_aiohttp(session: aiohttp.ClientSession, url: str, timeout_seconds=15) -> str:
    """Async HTTP fetch with aiohttp for better performance"""
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        async with session.get(url, timeout=timeout) as response:
            if response.status < 400:
                return await response.text()
    except Exception:
        pass
    return ""

async def fetch_with_playwright(url: str, timeout=30000):
    """Fallback to playwright for JS-heavy sites"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=timeout)
            content = await page.content()
            await browser.close()
            return content
    except Exception:
        return ""

async def scrape_job_details(session: aiohttp.ClientSession, job_url: str, title: str) -> Optional[Dict]:
    """Async job detail scraping"""
    try:
        html = await fetch_with_aiohttp(session, job_url, timeout_seconds=10)
        if not html:
            return None
            
        desc_text = BeautifulSoup(html, "html.parser").get_text(separator="\n")
        h = hashlib.sha256(desc_text.encode("utf-8")).hexdigest()
        
        return {
            "external_id": h[:12],
            "title": title,
            "description": desc_text,
            "apply_url": job_url,
            "raw_hash": h
        }
    except Exception:
        return None

async def scrape_company_jobs(company: Company, session: aiohttp.ClientSession = None):
    """Optimized async job scraping with concurrent processing"""
    careers = company.careers_url or company.homepage
    print(f"Scraping jobs for {company.name} from {careers}")
    
    if not careers:
        return []
    
    # Handle vendor-specific sites (these are usually fast)
    try:
        if "boards.greenhouse.io" in careers or "greenhouse.io" in careers:
            return greenhouse_list_jobs(careers)
        if "jobs.lever.co" in careers or "lever.co" in careers:
            return lever_list_jobs(careers)
    except Exception:
        pass

    # Create session if not provided
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=aiohttp.ClientTimeout(total=15)
        )
        close_session = True
    
    try:
        # Try aiohttp first, fallback to playwright for JS-heavy sites
        html = await fetch_with_aiohttp(session, careers, timeout_seconds=15)
        if not html:
            html = await fetch_with_playwright(careers)
        
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a", href=True)
        
        # Pre-filter job links
        job_candidates = []
        for a in anchors:
            title = (a.get_text() or "").strip()
            href = a["href"]
            
            if not title or len(title) < 3 or len(title) > 200:
                continue
                
            # Create absolute URL
            if not href.startswith("http"):
                job_url = requests.compat.urljoin(careers, href)
            else:
                job_url = href
            
            # Quick title filter
            if looks_like_engineering(title):
                job_candidates.append((job_url, title))
        
        # Limit concurrent job detail fetches to avoid overwhelming servers
        max_concurrent_jobs = min(20, len(job_candidates))
        job_candidates = job_candidates[:max_concurrent_jobs]
        
        # Fetch job details concurrently
        tasks = [scrape_job_details(session, job_url, title) for job_url, title in job_candidates]
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Filter out None results and exceptions
            valid_jobs = [job for job in results if job and not isinstance(job, Exception)]
            return valid_jobs
        
        return []
        
    finally:
        if close_session:
            await session.close()

async def scrape_company_batch(companies: List[Company], batch_id: int) -> Dict:
    """Scrape a batch of companies concurrently"""
    print(f"Processing batch {batch_id} with {len(companies)} companies")
    
    # Create shared aiohttp session for the batch
    async with aiohttp.ClientSession(
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=aiohttp.ClientTimeout(total=20),
        connector=aiohttp.TCPConnector(limit=10, limit_per_host=3)
    ) as session:
        
        # Process companies in this batch concurrently
        tasks = [scrape_company_jobs(comp, session) for comp in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        batch_results = {}
        for i, (comp, result) in enumerate(zip(companies, results)):
            if isinstance(result, Exception):
                print(f"Error scraping {comp.name}: {result}")
                batch_results[comp.id] = []
            else:
                print(f"Found {len(result)} jobs for {comp.name}")
                batch_results[comp.id] = result
        
        return batch_results

def store_jobs_batch(company_jobs_dict: Dict, companies: List[Company]) -> int:
    """Store jobs for a batch of companies using optimized DB operations"""
    db = SessionLocal()
    added_count = 0
    
    try:
        for company in companies:
            jobs = company_jobs_dict.get(company.id, [])
            
            if not jobs:
                continue
                
            # Batch check for existing jobs
            external_ids = [j["external_id"] for j in jobs]
            if len(external_ids) == 1:
                # Handle single item case
                existing_jobs = db.execute(
                    text("SELECT external_id FROM jobs WHERE company_id = :company_id AND external_id = :external_id"),
                    {"company_id": company.id, "external_id": external_ids[0]}
                ).fetchall()
            else:
                # Handle multiple items case
                placeholders = ",".join([":id" + str(i) for i in range(len(external_ids))])
                params = {"company_id": company.id}
                params.update({f"id{i}": ext_id for i, ext_id in enumerate(external_ids)})
                
                existing_jobs = db.execute(
                    text(f"SELECT external_id FROM jobs WHERE company_id = :company_id AND external_id IN ({placeholders})"),
                    params
                ).fetchall()
            
            existing_ids = {row[0] for row in existing_jobs}
            
            # Insert new jobs in batch
            new_jobs = [
                {
                    "company_id": company.id,
                    "external_id": j["external_id"],
                    "title": j["title"],
                    "description": j["description"][:5000],  # Truncate long descriptions
                    "apply_url": j["apply_url"],
                    "raw_hash": j["raw_hash"]
                }
                for j in jobs if j["external_id"] not in existing_ids
            ]
            
            if new_jobs:
                db.execute(
                    text("""
                    INSERT INTO jobs (company_id, external_id, title, description, apply_url, raw_hash, created_at)
                    VALUES (:company_id, :external_id, :title, :description, :apply_url, :raw_hash, datetime('now'))
                    """),
                    new_jobs
                )
                added_count += len(new_jobs)
        
        db.commit()
        print(f"Stored {added_count} new jobs in batch")
        
    except Exception as e:
        db.rollback()
        print(f"Error storing jobs batch: {e}")
    finally:
        db.close()
    
    return added_count

async def crawl_all_companies_optimized(save_to_db=True, max_workers=3, batch_size=5):
    """Optimized company crawling with concurrent processing"""
    db = SessionLocal()
    companies = db.query(Company).all()
    db.close()
    
    if not companies:
        print("No companies found to scrape")
        return 0
    
    print(f"Starting optimized crawl of {len(companies)} companies")
    print(f"Using {max_workers} workers with batch size {batch_size}")
    
    total_added = 0
    
    # Process companies in batches
    for i in range(0, len(companies), batch_size):
        batch = companies[i:i + batch_size]
        batch_id = i // batch_size + 1
        
        try:
            # Scrape this batch
            batch_results = await scrape_company_batch(batch, batch_id)
            
            # Store results
            if save_to_db:
                added = store_jobs_batch(batch_results, batch)
                total_added += added
            
            # Brief pause between batches to be respectful
            if i + batch_size < len(companies):
                await asyncio.sleep(2)
                
        except Exception as e:
            print(f"Error processing batch {batch_id}: {e}")
    
    print(f"\nCrawling complete! Added {total_added} new jobs total")
    return total_added

# Legacy function for backward compatibility
async def crawl_all_companies(save_to_db=True):
    """Legacy function - now uses optimized version"""
    return await crawl_all_companies_optimized(save_to_db=save_to_db)
