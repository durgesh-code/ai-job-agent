# src/monitoring/notification_service.py
import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import UserProfile, Notification, Job
from ..config import config

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications via email, SMS, etc."""
    
    def __init__(self):
        self.email_config = config.notification_config.get("email", {})
        self.enabled = config.notification_config.get("enabled", True)
    
    async def send_daily_digest(self, user_id: int):
        """Send daily digest of new job matches"""
        if not self.enabled:
            return
        
        db = SessionLocal()
        try:
            user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
            if not user or not user.email:
                return
            
            # Get unread notifications from last 24 hours
            notifications = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            ).all()
            
            if not notifications:
                return
            
            # Group notifications by type
            new_matches = [n for n in notifications if n.type == "new_job_match"]
            job_updates = [n for n in notifications if n.type == "job_updated"]
            
            # Create email content
            subject = f"Daily Job Digest - {len(new_matches)} new matches"
            html_content = self.create_digest_html(user, new_matches, job_updates)
            
            # Send email
            await self.send_email(user.email, subject, html_content)
            
            # Mark notifications as sent
            for notification in notifications:
                notification.is_sent = True
            
            db.commit()
            logger.info(f"Sent daily digest to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending daily digest: {e}")
        finally:
            db.close()
    
    async def send_instant_notification(self, notification_id: int):
        """Send instant notification for high-priority matches"""
        if not self.enabled:
            return
        
        db = SessionLocal()
        try:
            notification = db.query(Notification).filter(
                Notification.id == notification_id
            ).first()
            
            if not notification or not notification.user.email:
                return
            
            # Only send instant notifications for high-match jobs
            if notification.type == "new_job_match" and notification.job:
                # Check if this is a high-priority match
                match_score = self.extract_match_score(notification.message)
                if match_score and match_score >= 85:  # 85%+ match
                    subject = f"🎯 High Match Alert: {notification.job.title}"
                    html_content = self.create_instant_notification_html(notification)
                    
                    await self.send_email(notification.user.email, subject, html_content)
                    notification.is_sent = True
                    db.commit()
                    
                    logger.info(f"Sent instant notification to {notification.user.email}")
        
        except Exception as e:
            logger.error(f"Error sending instant notification: {e}")
        finally:
            db.close()
    
    def extract_match_score(self, message: str) -> Optional[float]:
        """Extract match score from notification message"""
        try:
            import re
            match = re.search(r'\((\d+)% match\)', message)
            if match:
                return float(match.group(1))
        except:
            pass
        return None
    
    def create_digest_html(self, user: UserProfile, new_matches: List[Notification], 
                          job_updates: List[Notification]) -> str:
        """Create HTML content for daily digest email"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Daily Job Digest</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #007bff; color: white; padding: 20px; text-align: center; }}
                .job-card {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }}
                .match-score {{ background: #28a745; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; }}
                .btn {{ background: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🤖 AI Job Agent</h1>
                    <p>Your Daily Job Digest</p>
                </div>
                
                <h2>Hello {user.name or 'there'}!</h2>
                <p>Here's your personalized job update for today:</p>
        """
        
        if new_matches:
            html += f"""
                <h3>🎯 New Job Matches ({len(new_matches)})</h3>
            """
            for notification in new_matches[:5]:  # Limit to top 5
                job = notification.job
                match_score = self.extract_match_score(notification.message) or 0
                html += f"""
                    <div class="job-card">
                        <h4>{job.title}</h4>
                        <p><strong>{job.company.name if job.company else 'Unknown Company'}</strong></p>
                        <p>📍 {job.location or 'Remote'} | 💼 {job.experience_level or 'Not specified'}</p>
                        <p><span class="match-score">{match_score:.0f}% Match</span></p>
                        <a href="http://localhost:8000/job/{job.id}" class="btn">View Job Details</a>
                    </div>
                """
        
        if job_updates:
            html += f"""
                <h3>📝 Job Updates ({len(job_updates)})</h3>
                <ul>
            """
            for notification in job_updates:
                html += f"<li>{notification.message}</li>"
            html += "</ul>"
        
        html += f"""
                <div class="footer">
                    <p>Visit your <a href="http://localhost:8000">AI Job Agent Dashboard</a> to see all matches and apply to jobs.</p>
                    <p>You received this email because you have notifications enabled in your AI Job Agent settings.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def create_instant_notification_html(self, notification: Notification) -> str:
        """Create HTML content for instant notification email"""
        job = notification.job
        match_score = self.extract_match_score(notification.message) or 0
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>High Match Job Alert</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .alert {{ background: #28a745; color: white; padding: 20px; text-align: center; border-radius: 5px; }}
                .job-details {{ background: #f8f9fa; padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .btn {{ background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 10px 5px; }}
                .btn-success {{ background: #28a745; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="alert">
                    <h1>🎯 High Match Alert!</h1>
                    <h2>{match_score:.0f}% Match Found</h2>
                </div>
                
                <div class="job-details">
                    <h2>{job.title}</h2>
                    <h3>{job.company.name if job.company else 'Company'}</h3>
                    <p><strong>Location:</strong> {job.location or 'Remote'}</p>
                    <p><strong>Experience:</strong> {job.experience_level or 'Not specified'}</p>
                    {f'<p><strong>Salary:</strong> ${job.salary_min:,} - ${job.salary_max:,}</p>' if job.salary_min and job.salary_max else ''}
                    
                    {f'<p><strong>Description:</strong> {job.description[:200]}...</p>' if job.description else ''}
                </div>
                
                <div style="text-align: center;">
                    <a href="http://localhost:8000/job/{job.id}" class="btn">View Full Details</a>
                    {f'<a href="{job.apply_url}" class="btn btn-success">Apply Now</a>' if job.apply_url else ''}
                </div>
                
                <p style="text-align: center; margin-top: 30px; color: #666; font-size: 12px;">
                    This high-priority alert was sent because this job matches your profile with {match_score:.0f}% accuracy.
                </p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    async def send_email(self, to_email: str, subject: str, html_content: str):
        """Send email notification"""
        try:
            # Check if email is configured
            if not self.email_config.get("smtp_server"):
                logger.warning("Email not configured, skipping email notification")
                return
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_config.get("from_email", "noreply@jobagent.ai")
            msg['To'] = to_email
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(
                self.email_config.get("smtp_server"),
                self.email_config.get("smtp_port", 587)
            ) as server:
                if self.email_config.get("use_tls", True):
                    server.starttls()
                
                if self.email_config.get("username"):
                    server.login(
                        self.email_config["username"],
                        self.email_config["password"]
                    )
                
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
    
    async def send_weekly_summary(self, user_id: int):
        """Send weekly summary of job market activity"""
        if not self.enabled:
            return
        
        db = SessionLocal()
        try:
            user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
            if not user or not user.email:
                return
            
            # Get weekly stats
            week_start = datetime.utcnow().replace(hour=0, minute=0, second=0) - timedelta(days=7)
            
            # Count new jobs this week
            new_jobs_count = db.query(Job).filter(
                Job.created_at >= week_start
            ).count()
            
            # Count user's matches this week
            user_matches_count = db.query(Notification).filter(
                Notification.user_id == user_id,
                Notification.type == "new_job_match",
                Notification.created_at >= week_start
            ).count()
            
            subject = f"Weekly Job Market Summary - {new_jobs_count} new jobs"
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1>📊 Weekly Job Market Summary</h1>
                    <p>Hello {user.name or 'there'}!</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 5px;">
                        <h3>This Week's Activity</h3>
                        <ul>
                            <li><strong>{new_jobs_count}</strong> new jobs added to the platform</li>
                            <li><strong>{user_matches_count}</strong> jobs matched your profile</li>
                        </ul>
                    </div>
                    
                    <p style="text-align: center; margin-top: 30px;">
                        <a href="http://localhost:8000/matches" style="background: #007bff; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px;">
                            View Your Matches
                        </a>
                    </p>
                </div>
            </body>
            </html>
            """
            
            await self.send_email(user.email, subject, html_content)
            logger.info(f"Sent weekly summary to {user.email}")
            
        except Exception as e:
            logger.error(f"Error sending weekly summary: {e}")
        finally:
            db.close()

# Global notification service instance
notification_service = NotificationService()
