# src/performance/background_jobs.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from celery import Celery
from celery.schedules import crontab
import os

from ..db import SessionLocal
from ..models import Job, Company, UserProfile
from ..crawler.company_finder import company_finder
from ..crawler.scraper import JobScraper
from ..aggregation.job_aggregator import job_aggregator
from ..matcher.enhanced_matcher import enhanced_matcher
from ..intelligence.company_analyzer import company_analyzer
from ..monitoring.notification_service import notification_service
from ..performance.cache_manager import cache_manager, warm_cache, cleanup_expired_cache
from ..config import config

logger = logging.getLogger(__name__)

# Initialize Celery
celery_config = config.performance_config.get("celery", {})
broker_url = celery_config.get("broker_url", "redis://localhost:6379/0")
result_backend = celery_config.get("result_backend", "redis://localhost:6379/0")

celery_app = Celery(
    'job_agent',
    broker=broker_url,
    backend=result_backend,
    include=['src.performance.background_jobs']
)

# Celery configuration
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    task_default_retry_delay=60,
    task_max_retries=3
)

# Periodic task schedule
celery_app.conf.beat_schedule = {
    # Job aggregation every 2 hours
    'aggregate-trending-jobs': {
        'task': 'src.performance.background_jobs.aggregate_trending_jobs_task',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # Company discovery daily at 2 AM
    'discover-companies': {
        'task': 'src.performance.background_jobs.discover_companies_task',
        'schedule': crontab(hour=2, minute=0),
    },
    # Job matching every 4 hours
    'refresh-job-matches': {
        'task': 'src.performance.background_jobs.refresh_job_matches_task',
        'schedule': crontab(minute=0, hour='*/4'),
    },
    # Company intelligence analysis daily at 3 AM
    'analyze-companies': {
        'task': 'src.performance.background_jobs.analyze_companies_task',
        'schedule': crontab(hour=3, minute=0),
    },
    # Cache warming every 6 hours
    'warm-cache': {
        'task': 'src.performance.background_jobs.warm_cache_task',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    # Cleanup tasks daily at 1 AM
    'cleanup-old-data': {
        'task': 'src.performance.background_jobs.cleanup_old_data_task',
        'schedule': crontab(hour=1, minute=0),
    },
    # Send daily digests at 9 AM
    'send-daily-digests': {
        'task': 'src.performance.background_jobs.send_daily_digests_task',
        'schedule': crontab(hour=9, minute=0),
    },
}

@celery_app.task(bind=True, name='src.performance.background_jobs.aggregate_trending_jobs_task')
def aggregate_trending_jobs_task(self):
    """Background task to aggregate trending jobs"""
    try:
        logger.info("Starting trending jobs aggregation task")
        
        # Run the aggregation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(job_aggregator.aggregate_trending_jobs(limit=200))
        
        logger.info(f"Trending jobs aggregation completed: {result.get('total_jobs_saved', 0)} jobs saved")
        
        return {
            'status': 'success',
            'jobs_saved': result.get('total_jobs_saved', 0),
            'sources': list(result.get('sources', {}).keys())
        }
        
    except Exception as e:
        logger.error(f"Error in trending jobs aggregation task: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=3)

@celery_app.task(bind=True, name='src.performance.background_jobs.discover_companies_task')
def discover_companies_task(self):
    """Background task to discover new companies"""
    try:
        logger.info("Starting company discovery task")
        
        # Discover companies across different categories
        keywords = [
            "software companies", "tech startups", "fintech companies",
            "healthcare technology", "e-commerce companies", "saas companies"
        ]
        
        total_discovered = 0
        for keyword in keywords:
            try:
                companies = company_finder.search_companies(keyword, limit=20)
                discovered_count = company_finder.discover_and_store_companies(companies)
                total_discovered += discovered_count
                
                # Add delay between searches
                import time
                time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error discovering companies for '{keyword}': {e}")
                continue
        
        logger.info(f"Company discovery completed: {total_discovered} companies discovered")
        
        return {
            'status': 'success',
            'companies_discovered': total_discovered,
            'keywords_processed': len(keywords)
        }
        
    except Exception as e:
        logger.error(f"Error in company discovery task: {e}")
        raise self.retry(exc=e, countdown=600, max_retries=2)

@celery_app.task(bind=True, name='src.performance.background_jobs.refresh_job_matches_task')
def refresh_job_matches_task(self):
    """Background task to refresh job matches for all users"""
    try:
        logger.info("Starting job matches refresh task")
        
        db = SessionLocal()
        users = db.query(UserProfile).filter(UserProfile.skills.isnot(None)).all()
        db.close()
        
        total_matches = 0
        for user in users:
            try:
                matches = enhanced_matcher.match_user_to_jobs(user.id, limit=50)
                total_matches += len(matches)
            except Exception as e:
                logger.error(f"Error matching jobs for user {user.id}: {e}")
                continue
        
        logger.info(f"Job matches refresh completed: {total_matches} matches generated for {len(users)} users")
        
        return {
            'status': 'success',
            'users_processed': len(users),
            'total_matches': total_matches
        }
        
    except Exception as e:
        logger.error(f"Error in job matches refresh task: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=3)

@celery_app.task(bind=True, name='src.performance.background_jobs.analyze_companies_task')
def analyze_companies_task(self):
    """Background task to analyze companies with intelligence"""
    try:
        logger.info("Starting company analysis task")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(company_analyzer.batch_analyze_companies(limit=20))
        
        analyzed_count = len([r for r in results if r.get('company_id')])
        
        logger.info(f"Company analysis completed: {analyzed_count} companies analyzed")
        
        return {
            'status': 'success',
            'companies_analyzed': analyzed_count,
            'total_results': len(results)
        }
        
    except Exception as e:
        logger.error(f"Error in company analysis task: {e}")
        raise self.retry(exc=e, countdown=900, max_retries=2)

@celery_app.task(bind=True, name='src.performance.background_jobs.warm_cache_task')
def warm_cache_task(self):
    """Background task to warm up cache"""
    try:
        logger.info("Starting cache warming task")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        loop.run_until_complete(cache_manager.initialize())
        loop.run_until_complete(warm_cache())
        
        # Get cache stats
        stats = loop.run_until_complete(cache_manager.get_stats())
        
        logger.info(f"Cache warming completed: {stats.get('total_keys', 0)} keys cached")
        
        return {
            'status': 'success',
            'cache_stats': stats
        }
        
    except Exception as e:
        logger.error(f"Error in cache warming task: {e}")
        raise self.retry(exc=e, countdown=180, max_retries=3)

@celery_app.task(bind=True, name='src.performance.background_jobs.cleanup_old_data_task')
def cleanup_old_data_task(self):
    """Background task to cleanup old data"""
    try:
        logger.info("Starting data cleanup task")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Cleanup old jobs
        old_jobs_count = loop.run_until_complete(job_aggregator.cleanup_old_jobs(days=90))
        
        # Cleanup expired cache
        loop.run_until_complete(cleanup_expired_cache())
        
        # Cleanup old notifications (older than 30 days)
        db = SessionLocal()
        try:
            from ..models import Notification
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            deleted_notifications = db.query(Notification).filter(
                Notification.created_at < cutoff_date,
                Notification.is_read == True
            ).delete()
            
            db.commit()
        finally:
            db.close()
        
        logger.info(f"Data cleanup completed: {old_jobs_count} jobs, {deleted_notifications} notifications")
        
        return {
            'status': 'success',
            'old_jobs_cleaned': old_jobs_count,
            'notifications_cleaned': deleted_notifications
        }
        
    except Exception as e:
        logger.error(f"Error in data cleanup task: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)

@celery_app.task(bind=True, name='src.performance.background_jobs.send_daily_digests_task')
def send_daily_digests_task(self):
    """Background task to send daily digest emails"""
    try:
        logger.info("Starting daily digest task")
        
        db = SessionLocal()
        users = db.query(UserProfile).filter(UserProfile.email.isnot(None)).all()
        db.close()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        sent_count = 0
        for user in users:
            try:
                loop.run_until_complete(notification_service.send_daily_digest(user.id))
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending daily digest to user {user.id}: {e}")
                continue
        
        logger.info(f"Daily digest task completed: {sent_count} digests sent")
        
        return {
            'status': 'success',
            'digests_sent': sent_count,
            'total_users': len(users)
        }
        
    except Exception as e:
        logger.error(f"Error in daily digest task: {e}")
        raise self.retry(exc=e, countdown=300, max_retries=2)

# Utility functions for manual task execution
class BackgroundJobManager:
    """Manager for background jobs and task monitoring"""
    
    @staticmethod
    def get_task_status(task_id: str) -> Dict:
        """Get status of a background task"""
        try:
            result = celery_app.AsyncResult(task_id)
            return {
                'task_id': task_id,
                'status': result.status,
                'result': result.result,
                'traceback': result.traceback
            }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def queue_job_aggregation() -> str:
        """Queue job aggregation task manually"""
        task = aggregate_trending_jobs_task.delay()
        return task.id
    
    @staticmethod
    def queue_company_discovery() -> str:
        """Queue company discovery task manually"""
        task = discover_companies_task.delay()
        return task.id
    
    @staticmethod
    def queue_match_refresh() -> str:
        """Queue job match refresh task manually"""
        task = refresh_job_matches_task.delay()
        return task.id
    
    @staticmethod
    def queue_company_analysis() -> str:
        """Queue company analysis task manually"""
        task = analyze_companies_task.delay()
        return task.id
    
    @staticmethod
    def get_worker_stats() -> Dict:
        """Get Celery worker statistics"""
        try:
            inspect = celery_app.control.inspect()
            return {
                'active_tasks': inspect.active(),
                'scheduled_tasks': inspect.scheduled(),
                'reserved_tasks': inspect.reserved(),
                'worker_stats': inspect.stats()
            }
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def get_queue_length() -> Dict:
        """Get queue lengths for different task types"""
        try:
            inspect = celery_app.control.inspect()
            reserved = inspect.reserved()
            active = inspect.active()
            
            queue_stats = {}
            for worker, tasks in (reserved or {}).items():
                queue_stats[worker] = len(tasks)
            
            return {
                'queue_lengths': queue_stats,
                'active_tasks': sum(len(tasks) for tasks in (active or {}).values()),
                'total_reserved': sum(len(tasks) for tasks in (reserved or {}).values())
            }
        except Exception as e:
            return {'error': str(e)}

# Global background job manager
background_job_manager = BackgroundJobManager()
