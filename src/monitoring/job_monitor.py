# src/monitoring/job_monitor.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..db import SessionLocal
from ..models import Job, Company, UserProfile, Notification, Match
from ..crawler.scraper import JobScraper
from ..matcher.enhanced_matcher import enhanced_matcher
from ..config import config

logger = logging.getLogger(__name__)

class JobMonitor:
    """Real-time job monitoring with incremental updates and alerts"""
    
    def __init__(self):
        self.scraper = JobScraper()
        self.monitoring_config = config.monitoring_config
        self.notification_config = config.notification_config
        self.is_running = False
        self.last_check = None
        
    async def start_monitoring(self):
        """Start the job monitoring loop"""
        self.is_running = True
        logger.info("Starting job monitoring...")
        
        while self.is_running:
            try:
                await self.check_for_updates()
                
                # Wait for next check interval
                interval = self.monitoring_config.get("check_interval_minutes", 30)
                await asyncio.sleep(interval * 60)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def stop_monitoring(self):
        """Stop the job monitoring"""
        self.is_running = False
        logger.info("Stopping job monitoring...")
    
    async def check_for_updates(self):
        """Check for new jobs and updates"""
        logger.info("Checking for job updates...")
        
        db = SessionLocal()
        try:
            # Get companies to monitor
            companies = self.get_companies_to_monitor(db)
            
            if not companies:
                logger.info("No companies to monitor")
                return
            
            # Check for new jobs
            new_jobs = await self.check_new_jobs(db, companies)
            
            # Check for job updates
            updated_jobs = await self.check_job_updates(db)
            
            # Process notifications
            if new_jobs or updated_jobs:
                await self.process_notifications(db, new_jobs, updated_jobs)
            
            # Update last check time
            self.last_check = datetime.utcnow()
            
            logger.info(f"Monitoring complete: {len(new_jobs)} new jobs, {len(updated_jobs)} updated jobs")
            
        finally:
            db.close()
    
    def get_companies_to_monitor(self, db: Session) -> List[Company]:
        """Get companies that should be monitored"""
        # Monitor companies with recent activity or high scores
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        companies = db.query(Company).filter(
            or_(
                Company.last_scraped >= cutoff_date,
                Company.company_score >= 0.7,
                Company.created_at >= cutoff_date
            )
        ).limit(self.monitoring_config.get("max_companies_per_check", 50)).all()
        
        return companies
    
    async def check_new_jobs(self, db: Session, companies: List[Company]) -> List[Job]:
        """Check for new jobs at monitored companies"""
        new_jobs = []
        
        for company in companies:
            try:
                # Get existing job URLs to avoid duplicates
                existing_urls = set(
                    job.apply_url for job in company.jobs 
                    if job.apply_url
                )
                
                # Scrape jobs from company
                scraped_jobs = await self.scraper.scrape_company_jobs(company, limit=20)
                
                for job_data in scraped_jobs:
                    # Check if this is a new job
                    if job_data.get('apply_url') not in existing_urls:
                        job = Job(**job_data, company_id=company.id)
                        db.add(job)
                        new_jobs.append(job)
                
                # Update company last scraped time
                company.last_scraped = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error checking jobs for {company.name}: {e}")
                continue
        
        if new_jobs:
            db.commit()
            logger.info(f"Found {len(new_jobs)} new jobs")
        
        return new_jobs
    
    async def check_job_updates(self, db: Session) -> List[Job]:
        """Check for updates to existing jobs"""
        updated_jobs = []
        
        # Get recently posted jobs that might have updates
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        jobs_to_check = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.is_active == True,
                Job.apply_url.isnot(None)
            )
        ).limit(self.monitoring_config.get("max_jobs_per_update_check", 100)).all()
        
        for job in jobs_to_check:
            try:
                # Re-scrape job details
                updated_data = await self.scraper.scrape_job_details(job.apply_url)
                
                if updated_data:
                    # Check for significant changes
                    changes = self.detect_job_changes(job, updated_data)
                    
                    if changes:
                        # Update job with new data
                        for key, value in updated_data.items():
                            if hasattr(job, key) and value is not None:
                                setattr(job, key, value)
                        
                        job.updated_at = datetime.utcnow()
                        updated_jobs.append(job)
                        
                        logger.info(f"Updated job: {job.title} at {job.company.name}")
                
            except Exception as e:
                logger.error(f"Error updating job {job.id}: {e}")
                continue
        
        if updated_jobs:
            db.commit()
        
        return updated_jobs
    
    def detect_job_changes(self, job: Job, new_data: Dict) -> bool:
        """Detect if there are significant changes to a job"""
        significant_fields = [
            'title', 'description', 'salary_min', 'salary_max', 
            'location', 'remote_option', 'required_skills'
        ]
        
        for field in significant_fields:
            if field in new_data:
                old_value = getattr(job, field, None)
                new_value = new_data[field]
                
                if old_value != new_value:
                    return True
        
        return False
    
    async def process_notifications(self, db: Session, new_jobs: List[Job], updated_jobs: List[Job]):
        """Process notifications for new and updated jobs"""
        users = db.query(UserProfile).all()
        
        for user in users:
            await self.send_user_notifications(db, user, new_jobs, updated_jobs)
    
    async def send_user_notifications(self, db: Session, user: UserProfile, new_jobs: List[Job], updated_jobs: List[Job]):
        """Send notifications to a specific user"""
        notifications_sent = 0
        max_notifications = self.notification_config.get("max_notifications_per_user", 10)
        
        # Check new jobs for matches
        for job in new_jobs:
            if notifications_sent >= max_notifications:
                break
                
            # Calculate match score
            match_score = enhanced_matcher.calculate_job_match(user, job)
            
            # Send notification if match score is high enough
            min_score = self.notification_config.get("min_match_score_for_notification", 0.7)
            
            if match_score.overall_score >= min_score:
                await self.create_notification(
                    db, user, job, "new_job_match", 
                    f"New job match: {job.title} at {job.company.name} ({match_score.overall_score*100:.0f}% match)"
                )
                notifications_sent += 1
        
        # Check updated jobs for existing matches
        for job in updated_jobs:
            if notifications_sent >= max_notifications:
                break
                
            # Check if user has a match for this job
            existing_match = db.query(Match).filter(
                and_(Match.user_id == user.id, Match.job_id == job.id)
            ).first()
            
            if existing_match:
                await self.create_notification(
                    db, user, job, "job_updated",
                    f"Job updated: {job.title} at {job.company.name}"
                )
                notifications_sent += 1
    
    async def create_notification(self, db: Session, user: UserProfile, job: Job, 
                                notification_type: str, message: str):
        """Create a notification for a user"""
        notification = Notification(
            user_id=user.id,
            job_id=job.id,
            type=notification_type,
            title=f"Job Alert: {job.title}",
            message=message,
            is_read=False,
            created_at=datetime.utcnow()
        )
        
        db.add(notification)
        logger.info(f"Created notification for user {user.id}: {message}")
    
    async def cleanup_old_notifications(self, db: Session):
        """Clean up old notifications"""
        cutoff_date = datetime.utcnow() - timedelta(
            days=self.notification_config.get("notification_retention_days", 30)
        )
        
        deleted_count = db.query(Notification).filter(
            and_(
                Notification.created_at < cutoff_date,
                Notification.is_read == True
            )
        ).delete()
        
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old notifications")
    
    def get_monitoring_stats(self, db: Session) -> Dict:
        """Get monitoring statistics"""
        now = datetime.utcnow()
        
        # Jobs added in last 24 hours
        jobs_24h = db.query(Job).filter(
            Job.created_at >= now - timedelta(hours=24)
        ).count()
        
        # Jobs added in last week
        jobs_week = db.query(Job).filter(
            Job.created_at >= now - timedelta(days=7)
        ).count()
        
        # Active notifications
        active_notifications = db.query(Notification).filter(
            Notification.is_read == False
        ).count()
        
        # Companies monitored
        monitored_companies = len(self.get_companies_to_monitor(db))
        
        return {
            "is_running": self.is_running,
            "last_check": self.last_check,
            "jobs_added_24h": jobs_24h,
            "jobs_added_week": jobs_week,
            "active_notifications": active_notifications,
            "monitored_companies": monitored_companies
        }

# Global monitor instance
job_monitor = JobMonitor()

async def start_job_monitoring():
    """Start the job monitoring service"""
    await job_monitor.start_monitoring()

def stop_job_monitoring():
    """Stop the job monitoring service"""
    job_monitor.stop_monitoring()

def get_monitoring_status() -> Dict:
    """Get current monitoring status"""
    db = SessionLocal()
    try:
        return job_monitor.get_monitoring_stats(db)
    finally:
        db.close()
