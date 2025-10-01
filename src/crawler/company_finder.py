# src/crawler/company_finder.py
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from ..db import SessionLocal
from ..models import Company
import re
import time
import logging
import json
from datetime import datetime
from typing import List, Dict, Set, Tuple
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

# read from env
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "xxx")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "xxx")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "xxx"))

# Comprehensive search queries for different company types and sizes
SEARCH_QUERY_TEMPLATES = {
    "mnc_tech": [
        "multinational technology companies in {location}",
        "large tech corporations {location}",
        "fortune 500 technology companies {location}",
        "global software companies offices {location}",
        "enterprise software companies {location}"
    ],
    "startups": [
        "tech startups in {location}",
        "software startups {location}",
        "fintech startups {location}",
        "AI startups {location}",
        "SaaS startups {location}",
        "edtech startups {location}",
        "healthtech startups {location}"
    ],
    "medium_companies": [
        "mid-size software companies {location}",
        "medium technology companies {location}",
        "growing tech companies {location}",
        "scale-up companies {location}",
        "product companies {location}"
    ],
    "unicorns": [
        "unicorn companies {location}",
        "billion dollar startups {location}",
        "decacorn companies {location}"
    ],
    "specific_sectors": [
        "cybersecurity companies {location}",
        "cloud computing companies {location}",
        "data analytics companies {location}",
        "mobile app development companies {location}",
        "e-commerce companies {location}",
        "gaming companies {location}",
        "blockchain companies {location}"
    ]
}

def _google_search(query: str, num: int = 10):
    print("++++++++++++++++++++++++++++")
    print(GOOGLE_API_KEY)
    print(GOOGLE_CSE_ID)
    if not GOOGLE_API_KEY or not GOOGLE_CSE_ID:
        raise RuntimeError("Set GOOGLE_API_KEY and GOOGLE_CSE_ID env vars for discovery.")
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"q": query, "key": GOOGLE_API_KEY, "cx": GOOGLE_CSE_ID, "num": min(num, 10)}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])

def _llm_filter_companies(raw_results, company_type="general"):
    """Enhanced LLM filtering with company type awareness and rate limiting"""
    text_block = "\n".join(
        [f"- Title: {r.get('title')}\n  Link: {r.get('link')}\n  Snippet: {r.get('snippet','')}"
         for r in raw_results]
    )
    
    type_specific_instructions = {
        "mnc_tech": "Focus on large multinational technology corporations, Fortune 500 companies, and global tech giants.",
        "startups": "Focus on early-stage companies, funded startups, and emerging technology companies.",
        "medium_companies": "Focus on established mid-size companies, scale-ups, and growing technology firms.",
        "unicorns": "Focus on high-valuation private companies (unicorns/decacorns) and well-funded startups.",
        "specific_sectors": "Focus on specialized technology companies in specific domains like cybersecurity, AI, fintech, etc."
    }
    
    additional_instruction = type_specific_instructions.get(company_type, "Focus on legitimate technology and software companies.")
    
    prompt = f"""
    You are an assistant that filters Google search results for real software/tech companies.
    
    {additional_instruction}
    
    From the following list, keep only real software/technology companies with their *official homepage* URLs.
    Ignore blogs, news articles, consulting firms, job boards, or company directories.
    
    For each valid company, also try to determine:
    - Company size (startup/medium/large)
    - Primary sector (if identifiable)

    Output as JSON with "companies" array. Each item should have:
    {{
      "companies": [
        {{
          "name": "<company name>",
          "url": "<homepage URL>",
          "estimated_size": "<startup|medium|large>",
          "sector": "<primary technology sector>"
        }}
      ]
    }}
    
    Results:
    {text_block}
    """
    
    # Add delay to respect rate limits (3 requests per minute = 20 seconds between requests)
    time.sleep(21)  # Wait 21 seconds to be safe
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": "Be precise and return valid JSON only."},
                          {"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 30  # Exponential backoff: 30, 60, 90 seconds
                print(f"Rate limit hit, waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}")
                time.sleep(wait_time)
            else:
                raise e

def _process_search_query(query: str, category: str, seen_companies: Set, max_companies: int, lock: Lock) -> List[Dict]:
    """Process a single search query and return filtered companies (thread-safe)"""
    try:
        items = _google_search(query, num=10)
        if not items:
            return []
            
        filtered_json = _llm_filter_companies(items, company_type=category)
        companies_data = json.loads(filtered_json)
        companies = companies_data.get("companies", [])
        
        with lock:
            return _filter_unique_companies(companies, category, seen_companies, max_companies)
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response for query '{query}': {e}")
        return []
    except Exception as e:
        print(f"Search failed for query '{query}': {e}")
        return []

def _filter_unique_companies(companies: List[Dict], category: str, seen_companies: Set, max_companies: int) -> List[Dict]:
    """Filter companies to avoid duplicates and add metadata"""
    filtered_companies = []
    
    for company in companies:
        if len(filtered_companies) >= max_companies:
            break
            
        company_key = (company.get("name", "").lower(), company.get("url", ""))
        if company_key not in seen_companies and company.get("name") and company.get("url"):
            seen_companies.add(company_key)
            company["search_category"] = category
            filtered_companies.append(company)
    
    return filtered_companies

def _search_category_companies_threaded(category: str, queries: List[str], location: str, max_companies_per_type: int, seen_companies: Set, lock: Lock) -> List[Dict]:
    """Search companies for a specific category with sequential processing to avoid rate limits"""
    print(f"\n--- Searching {category} companies ---")
    category_companies = []
    
    # Process queries sequentially to avoid rate limits
    for i, query_template in enumerate(queries[:3]):  # Limit to 3 queries per category
        if len(category_companies) >= max_companies_per_type:
            break
            
        query = query_template.format(location=location)
        print(f"Searching: {query} ({i+1}/{min(3, len(queries))})")
        
        try:
            query_companies = _process_search_query(query, category, seen_companies, max_companies_per_type - len(category_companies), lock)
            category_companies.extend(query_companies)
            print(f"Completed search for: {query}")
        except Exception as e:
            print(f"Query failed: {query} - {e}")
        
        # Add delay between queries within the same category
        if i < min(2, len(queries) - 1):  # Don't wait after the last query
            print("Waiting 25 seconds before next query...")
            time.sleep(25)
    
    return category_companies[:max_companies_per_type]

def search_companies_comprehensive(location: str, max_companies_per_type: int = 20) -> List[Dict]:
    """
    Comprehensive company search across multiple categories with rate limiting
    """
    all_companies = []
    seen_companies = set()
    lock = Lock()
    
    print(f"Starting comprehensive company search for {location}...")
    print("Note: Processing sequentially to avoid API rate limits (3 requests/minute)")
    
    # Process categories sequentially to avoid rate limits
    for i, (category, queries) in enumerate(SEARCH_QUERY_TEMPLATES.items()):
        print(f"\nProcessing category {i+1}/{len(SEARCH_QUERY_TEMPLATES)}: {category}")
        
        try:
            category_companies = _search_category_companies_threaded(category, queries, location, max_companies_per_type, seen_companies, lock)
            all_companies.extend(category_companies)
            print(f"Found {len(category_companies)} companies in {category} category")
        except Exception as e:
            print(f"Category {category} failed: {e}")
        
        # Add delay between categories (except after the last one)
        if i < len(SEARCH_QUERY_TEMPLATES) - 1:
            print("Waiting 30 seconds before next category...")
            time.sleep(30)
    
    print(f"\nTotal unique companies found: {len(all_companies)}")
    return all_companies

def search_companies(location: str, num: int = 10) -> List[Dict]:
    """
    Legacy function maintained for backward compatibility
    Now uses comprehensive search but limits results
    """
    comprehensive_results = search_companies_comprehensive(location, max_companies_per_type=5)
    return comprehensive_results[:num]


def find_careers_url_from_homepage(homepage: str):
    try:
        r = requests.get(homepage, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    # look for explicit anchors
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip().lower()
        href = a["href"]
        if any(k in text for k in ["careers", "jobs", "work with us", "join us", "open roles", "positions"]):
            return urljoin(homepage, href)
    # look for vendor domains (greenhouse, lever)
    if "greenhouse.io" in r.text:
        # try to find actual greenhouse link or fallback to platform root
        for a in soup.find_all("a", href=True):
            if "boards.greenhouse.io" in a["href"]:
                return a["href"]
        return None
    if "jobs.lever.co" in r.text or "lever.co" in r.text:
        for a in soup.find_all("a", href=True):
            if "jobs.lever.co" in a["href"]:
                return a["href"]
        return None
    # fallback: try homepage + '/careers' or '/jobs'
    for suffix in ["/careers","/jobs","/company/jobs","/careers/"]:
        candidate = urljoin(homepage, suffix)
        try:
            rr = requests.head(candidate, timeout=8)
            if rr.status_code < 400:
                return candidate
        except Exception:
            continue
    return None

def _process_company_batch(companies_batch: List[Dict]) -> Tuple[List[Company], int]:
    """Process a batch of companies and find their careers URLs"""
    processed_companies = []
    processed_count = 0
    
    def process_single_company(company_data):
        name = company_data.get("name")
        homepage = company_data.get("url")
        
        if not name or not homepage:
            return None
            
        print(f"Processing: {name}")
        
        # Find careers URL
        careers = find_careers_url_from_homepage(homepage)
        
        # Create company record with additional metadata
        comp = Company(
            name=name, 
            homepage=homepage, 
            careers_url=careers
        )
        
        # Store additional metadata in meta_info as JSON
        meta_info = {
            "estimated_size": company_data.get("estimated_size", "unknown"),
            "sector": company_data.get("sector", "technology"),
            "search_category": company_data.get("search_category", "general")
        }
        comp.meta_info = json.dumps(meta_info)
        
        return comp
    
    # Process companies in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_company = {executor.submit(process_single_company, company_data): company_data for company_data in companies_batch}
        
        for future in as_completed(future_to_company):
            try:
                result = future.result()
                if result:
                    processed_companies.append(result)
                    processed_count += 1
            except Exception as e:
                company_data = future_to_company[future]
                print(f"Failed to process company {company_data.get('name', 'Unknown')}: {e}")
    
    return processed_companies, processed_count

def discover_and_store_companies(location: str, comprehensive: bool = True, max_per_category: int = 20):
    """
    Discover and store companies with option for comprehensive search and multithreading optimization
    
    Args:
        location: Geographic location to search
        comprehensive: If True, uses comprehensive search across all categories
        max_per_category: Maximum companies per category (only used if comprehensive=True)
    """
    if comprehensive:
        print(f"Starting comprehensive company discovery for {location}")
        hits = search_companies_comprehensive(location, max_companies_per_type=max_per_category)
    else:
        print(f"Starting basic company discovery for {location}")
        hits = search_companies(location, num=50)  # Increased from 10 for better coverage
    
    if not hits:
        print("No companies found to process")
        return 0
    
    db = SessionLocal()
    added = 0
    skipped = 0
    
    try:
        # Process companies in batches
        batch_size = 10
        for i in range(0, len(hits), batch_size):
            batch = hits[i:i + batch_size]
            print(f"\nProcessing batch {i//batch_size + 1}/{(len(hits) + batch_size - 1)//batch_size}")
            
            processed_companies, _ = _process_company_batch(batch)
            
            # Store companies using INSERT OR IGNORE to handle duplicates
            for comp in processed_companies:
                try:
                    # Use raw SQL with INSERT OR IGNORE to handle duplicates gracefully
                    result = db.execute(
                        text("""
                        INSERT OR IGNORE INTO companies (name, homepage, careers_url, meta_info, created_at) 
                        VALUES (:name, :homepage, :careers_url, :meta_info, :created_at)
                        """),
                        {
                            "name": comp.name,
                            "homepage": comp.homepage, 
                            "careers_url": comp.careers_url,
                            "meta_info": comp.meta_info,
                            "created_at": comp.created_at or datetime.now()
                        }
                    )
                    
                    if result.rowcount > 0:
                        added += 1
                        print(f"Added: {comp.name}")
                    else:
                        skipped += 1
                        print(f"Skipped (duplicate): {comp.name}")
                        
                except Exception as e:
                    print(f"Failed to store company {comp.name}: {e}")
                    skipped += 1
            
            # Commit batch
            db.commit()
            print(f"Batch committed: {len(processed_companies)} companies processed")
            
        print(f"\nDiscovery complete: {added} companies added, {skipped} already existed or failed")
        
    except Exception as e:
        db.rollback()
        print(f"Error during company discovery: {e}")
        raise
    finally:
        db.close()
    
    return added

def discover_and_store_companies_legacy(location: str, _num: int = 10):
    """Legacy function for backward compatibility"""
    return discover_and_store_companies(location, comprehensive=False)

def get_company_search_stats(location: str) -> Dict:
    """
    Get statistics about companies that would be found in a comprehensive search
    without actually storing them to the database
    """
    companies = search_companies_comprehensive(location, max_companies_per_type=10)
    
    stats = {
        "total_companies": len(companies),
        "by_category": {},
        "by_size": {},
        "by_sector": {}
    }
    
    for company in companies:
        # Count by search category
        category = company.get("search_category", "unknown")
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        
        # Count by estimated size
        size = company.get("estimated_size", "unknown")
        stats["by_size"][size] = stats["by_size"].get(size, 0) + 1
        
        # Count by sector
        sector = company.get("sector", "unknown")
        stats["by_sector"][sector] = stats["by_sector"].get(sector, 0) + 1
    
    return stats

if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        location = sys.argv[1]
    else:
        location = "Bangalore"
    
    print(f"Testing comprehensive company search for {location}")
    print("=" * 50)
    
    # Get search statistics
    stats = get_company_search_stats(location)
    
    print(f"Total companies found: {stats['total_companies']}")
    print("\nBy category:")
    for category, count in stats['by_category'].items():
        print(f"  {category}: {count}")
    
    print("\nBy estimated size:")
    for size, count in stats['by_size'].items():
        print(f"  {size}: {count}")
    
    print("\nBy sector:")
    for sector, count in stats['by_sector'].items():
        print(f"  {sector}: {count}")
    
    # Uncomment to actually store companies in database
    # added = discover_and_store_companies(location, comprehensive=True, max_per_category=15)
    # print(f"\nStored {added} companies to database")
