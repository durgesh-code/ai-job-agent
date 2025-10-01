# src/monitoring/scheduler.py
import asyncio
import logging
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .job_monitor import job_monitor
from .notification_service import notification_service
from ..db import SessionLocal
from ..models import UserProfile
from ..config import config

logger = logging.getLogger(__name__)

class MonitoringScheduler:
    """Scheduler for monitoring and notification tasks"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.monitoring_config = config.monitoring_config
        self.notification_config = config.notification_config
        
    def start(self):
        """Start the scheduler with all monitoring tasks"""
        logger.info("Starting monitoring scheduler...")
        
        # Job monitoring - check for new jobs every 30 minutes
        self.scheduler.add_job(
            job_monitor.check_for_updates,
            IntervalTrigger(minutes=self.monitoring_config.get("check_interval_minutes", 30)),
            id="job_monitoring",
            name="Job Monitoring",
            max_instances=1
        )
        
        # Daily digest - send at 9 AM every day
        self.scheduler.add_job(
            self.send_daily_digests,
            CronTrigger(hour=9, minute=0),
            id="daily_digest",
            name="Daily Digest",
            max_instances=1
        )
        
        # Weekly summary - send on Mondays at 10 AM
        self.scheduler.add_job(
            self.send_weekly_summaries,
            CronTrigger(day_of_week=0, hour=10, minute=0),
            id="weekly_summary",
            name="Weekly Summary",
            max_instances=1
        )
        
        # Cleanup old notifications - daily at midnight
        self.scheduler.add_job(
            self.cleanup_notifications,
            CronTrigger(hour=0, minute=0),
            id="cleanup_notifications",
            name="Cleanup Notifications",
            max_instances=1
        )
        
        # Health check - every hour
        self.scheduler.add_job(
            self.health_check,
            IntervalTrigger(hours=1),
            id="health_check",
            name="Health Check",
            max_instances=1
        )
        
        self.scheduler.start()
        logger.info("Monitoring scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping monitoring scheduler...")
        self.scheduler.shutdown()
    
    async def send_daily_digests(self):
        """Send daily digest to all users"""
        if not self.notification_config.get("daily_digest_enabled", True):
            return
        
        logger.info("Sending daily digests...")
        db = SessionLocal()
        try:
            users = db.query(UserProfile).filter(
                UserProfile.email.isnot(None)
            ).all()
            
            for user in users:
                try:
                    await notification_service.send_daily_digest(user.id)
                except Exception as e:
                    logger.error(f"Error sending daily digest to user {user.id}: {e}")
            
            logger.info(f"Daily digests sent to {len(users)} users")
            
        finally:
            db.close()
    
    async def send_weekly_summaries(self):
        """Send weekly summary to all users"""
        if not self.notification_config.get("weekly_summary_enabled", True):
            return
        
        logger.info("Sending weekly summaries...")
        db = SessionLocal()
        try:
            users = db.query(UserProfile).filter(
                UserProfile.email.isnot(None)
            ).all()
            
            for user in users:
                try:
                    await notification_service.send_weekly_summary(user.id)
                except Exception as e:
                    logger.error(f"Error sending weekly summary to user {user.id}: {e}")
            
            logger.info(f"Weekly summaries sent to {len(users)} users")
            
        finally:
            db.close()
    
    async def cleanup_notifications(self):
        """Clean up old notifications"""
        logger.info("Cleaning up old notifications...")
        db = SessionLocal()
        try:
            await job_monitor.cleanup_old_notifications(db)
        finally:
            db.close()
    
    async def health_check(self):
        """Perform health check on monitoring system"""
        try:
            db = SessionLocal()
            stats = job_monitor.get_monitoring_stats(db)
            db.close()
            
            # Log health status
            logger.info(f"Health check - Monitoring: {'✓' if stats['is_running'] else '✗'}, "
                       f"Jobs 24h: {stats['jobs_added_24h']}, "
                       f"Active notifications: {stats['active_notifications']}")
            
            # Alert if monitoring stopped
            if not stats['is_running']:
                logger.warning("Job monitoring is not running!")
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def get_job_status(self):
        """Get status of all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger)
            })
        return jobs

# Global scheduler instance
monitoring_scheduler = MonitoringScheduler()

def start_monitoring_scheduler():
    """Start the monitoring scheduler"""
    monitoring_scheduler.start()

def stop_monitoring_scheduler():
    """Stop the monitoring scheduler"""
    monitoring_scheduler.stop()

def get_scheduler_status():
    """Get scheduler status"""
    return {
        "running": monitoring_scheduler.scheduler.running,
        "jobs": monitoring_scheduler.get_job_status()
    }
