# src/aggregation/job_aggregator.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
import aiohttp
from urllib.parse import urlencode

from ..db import SessionLocal
from ..models import Job, Company
from ..config import config
from .linkedin_scraper import LinkedInScraper
from .indeed_scraper import IndeedScraper
from .angellist_scraper import AngelListScraper

logger = logging.getLogger(__name__)

class JobAggregator:
    """Multi-source job aggregation from various job boards"""
    
    def __init__(self):
        self.aggregation_config = config.aggregation_config
        self.linkedin_scraper = LinkedInScraper()
        self.indeed_scraper = IndeedScraper()
        self.angellist_scraper = AngelListScraper()
        
        # Track processed job URLs to avoid duplicates
        self.processed_urls: Set[str] = set()
    
    async def aggregate_jobs(self, keywords: List[str], locations: List[str], 
                           limit_per_source: int = 50) -> Dict:
        """Aggregate jobs from all configured sources"""
        logger.info(f"Starting job aggregation for keywords: {keywords}, locations: {locations}")
        
        results = {
            "aggregation_started": datetime.utcnow().isoformat(),
            "sources": {},
            "total_jobs_found": 0,
            "total_jobs_saved": 0,
            "duplicates_filtered": 0
        }
        
        # Load existing job URLs to avoid duplicates
        await self.load_existing_job_urls()
        
        # Aggregate from each source
        sources = []
        
        if self.aggregation_config.get("linkedin_enabled", False):
            sources.append(("LinkedIn", self.linkedin_scraper))
        
        if self.aggregation_config.get("indeed_enabled", True):
            sources.append(("Indeed", self.indeed_scraper))
        
        if self.aggregation_config.get("angellist_enabled", False):
            sources.append(("AngelList", self.angellist_scraper))
        
        for source_name, scraper in sources:
            try:
                logger.info(f"Aggregating from {source_name}...")
                source_results = await self.aggregate_from_source(
                    scraper, source_name, keywords, locations, limit_per_source
                )
                results["sources"][source_name] = source_results
                results["total_jobs_found"] += source_results.get("jobs_found", 0)
                results["total_jobs_saved"] += source_results.get("jobs_saved", 0)
                results["duplicates_filtered"] += source_results.get("duplicates_filtered", 0)
                
                # Add delay between sources to be respectful
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Error aggregating from {source_name}: {e}")
                results["sources"][source_name] = {"error": str(e)}
        
        results["aggregation_completed"] = datetime.utcnow().isoformat()
        logger.info(f"Job aggregation completed: {results['total_jobs_saved']} jobs saved")
        
        return results
    
    async def aggregate_from_source(self, scraper, source_name: str, 
                                  keywords: List[str], locations: List[str], 
                                  limit: int) -> Dict:
        """Aggregate jobs from a specific source"""
        jobs_found = 0
        jobs_saved = 0
        duplicates_filtered = 0
        errors = []
        
        db = SessionLocal()
        try:
            for keyword in keywords:
                for location in locations:
                    try:
                        # Search jobs from source
                        jobs = await scraper.search_jobs(
                            keyword=keyword,
                            location=location,
                            limit=limit // (len(keywords) * len(locations))
                        )
                        
                        jobs_found += len(jobs)
                        
                        for job_data in jobs:
                            # Check for duplicates
                            job_url = job_data.get('apply_url') or job_data.get('job_url')
                            if job_url in self.processed_urls:
                                duplicates_filtered += 1
                                continue
                            
                            # Save job to database
                            if await self.save_job_from_source(db, job_data, source_name):
                                jobs_saved += 1
                                if job_url:
                                    self.processed_urls.add(job_url)
                        
                        # Rate limiting
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        error_msg = f"Error searching {keyword} in {location}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Database error in {source_name} aggregation: {e}")
            errors.append(str(e))
        finally:
            db.close()
        
        return {
            "jobs_found": jobs_found,
            "jobs_saved": jobs_saved,
            "duplicates_filtered": duplicates_filtered,
            "errors": errors
        }
    
    async def save_job_from_source(self, db: Session, job_data: Dict, source: str) -> bool:
        """Save a job from external source to database"""
        try:
            # Get or create company
            company = await self.get_or_create_company(db, job_data.get('company_name'), job_data)
            
            # Create job object
            job = Job(
                title=job_data.get('title'),
                description=job_data.get('description'),
                company_id=company.id if company else None,
                location=job_data.get('location'),
                apply_url=job_data.get('apply_url') or job_data.get('job_url'),
                salary_min=job_data.get('salary_min'),
                salary_max=job_data.get('salary_max'),
                experience_level=job_data.get('experience_level'),
                remote_option=job_data.get('remote_option'),
                required_skills=job_data.get('required_skills'),
                benefits=job_data.get('benefits'),
                job_type=job_data.get('job_type', 'full_time'),
                source=source,
                external_id=job_data.get('external_id'),
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            db.add(job)
            return True
            
        except Exception as e:
            logger.error(f"Error saving job from {source}: {e}")
            return False
    
    async def get_or_create_company(self, db: Session, company_name: str, job_data: Dict) -> Optional[Company]:
        """Get existing company or create new one"""
        if not company_name:
            return None
        
        # Check if company exists
        company = db.query(Company).filter(Company.name == company_name).first()
        
        if not company:
            # Create new company
            company = Company(
                name=company_name,
                website=job_data.get('company_website'),
                location=job_data.get('company_location'),
                description=job_data.get('company_description'),
                industry=job_data.get('company_industry'),
                company_size=job_data.get('company_size'),
                created_at=datetime.utcnow()
            )
            db.add(company)
            db.flush()  # Get the ID
        
        return company
    
    async def load_existing_job_urls(self):
        """Load existing job URLs to avoid duplicates"""
        db = SessionLocal()
        try:
            # Load URLs from last 30 days to avoid duplicates
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            existing_urls = db.query(Job.apply_url).filter(
                Job.apply_url.isnot(None),
                Job.created_at >= cutoff_date
            ).all()
            
            self.processed_urls = {url[0] for url in existing_urls if url[0]}
            logger.info(f"Loaded {len(self.processed_urls)} existing job URLs")
            
        finally:
            db.close()
    
    async def aggregate_trending_jobs(self, limit: int = 100) -> Dict:
        """Aggregate trending/popular jobs from all sources"""
        trending_keywords = [
            "software engineer", "data scientist", "product manager",
            "frontend developer", "backend developer", "full stack",
            "devops engineer", "machine learning", "ai engineer"
        ]
        
        trending_locations = [
            "San Francisco", "New York", "Seattle", "Austin", "Remote"
        ]
        
        return await self.aggregate_jobs(
            keywords=trending_keywords,
            locations=trending_locations,
            limit_per_source=limit
        )
    
    async def aggregate_for_user_profile(self, user_skills: List[str], 
                                       user_locations: List[str], 
                                       limit: int = 50) -> Dict:
        """Aggregate jobs tailored to user profile"""
        # Use user skills as keywords
        keywords = user_skills[:5]  # Top 5 skills
        locations = user_locations[:3]  # Top 3 locations
        
        if not keywords:
            keywords = ["software engineer"]  # Default fallback
        
        if not locations:
            locations = ["Remote"]  # Default to remote
        
        return await self.aggregate_jobs(
            keywords=keywords,
            locations=locations,
            limit_per_source=limit
        )
    
    def get_aggregation_stats(self) -> Dict:
        """Get aggregation statistics"""
        db = SessionLocal()
        try:
            # Jobs by source in last 24 hours
            cutoff_24h = datetime.utcnow() - timedelta(hours=24)
            
            source_stats = {}
            sources = ["LinkedIn", "Indeed", "AngelList", "Google", "Company Website"]
            
            for source in sources:
                count = db.query(Job).filter(
                    Job.source == source,
                    Job.created_at >= cutoff_24h
                ).count()
                if count > 0:
                    source_stats[source] = count
            
            # Total jobs aggregated
            total_jobs = db.query(Job).count()
            
            # Jobs in last week
            cutoff_week = datetime.utcnow() - timedelta(days=7)
            jobs_week = db.query(Job).filter(Job.created_at >= cutoff_week).count()
            
            return {
                "total_jobs_in_database": total_jobs,
                "jobs_added_last_24h": sum(source_stats.values()),
                "jobs_added_last_week": jobs_week,
                "jobs_by_source_24h": source_stats,
                "processed_urls_count": len(self.processed_urls)
            }
            
        finally:
            db.close()
    
    async def cleanup_old_jobs(self, days: int = 90):
        """Clean up old inactive jobs"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Mark old jobs as inactive instead of deleting
            updated_count = db.query(Job).filter(
                Job.created_at < cutoff_date,
                Job.is_active == True
            ).update({"is_active": False})
            
            db.commit()
            
            logger.info(f"Marked {updated_count} old jobs as inactive")
            return updated_count
            
        finally:
            db.close()

# Global aggregator instance
job_aggregator = JobAggregator()
