# src/analytics/analytics_engine.py
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from collections import defaultdict
import json

from ..db import SessionLocal
from ..models import Job, Company, Match, UserProfile, JobApplication
from ..intelligence.market_analyzer import market_analyzer
from ..config import config

logger = logging.getLogger(__name__)

class AnalyticsEngine:
    """Comprehensive analytics and insights engine"""
    
    def __init__(self):
        self.analytics_config = config.analytics_config
    
    def generate_comprehensive_report(self, days: int = 30) -> Dict:
        """Generate comprehensive analytics report"""
        db = SessionLocal()
        try:
            report = {
                "report_generated": datetime.utcnow().isoformat(),
                "analysis_period_days": days,
                "market_trends": market_analyzer.analyze_job_market_trends(days),
                "platform_metrics": self.get_platform_metrics(db, days),
                "user_engagement": self.analyze_user_engagement(db, days),
                "job_performance": self.analyze_job_performance(db, days),
                "company_insights": self.analyze_company_performance(db, days),
                "matching_effectiveness": self.analyze_matching_effectiveness(db, days),
                "recommendations": self.generate_recommendations(db, days)
            }
            
            return report
            
        finally:
            db.close()
    
    def get_platform_metrics(self, db: Session, days: int) -> Dict:
        """Get key platform metrics"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Core metrics
        total_jobs = db.query(Job).count()
        active_jobs = db.query(Job).filter(Job.is_active == True).count()
        new_jobs = db.query(Job).filter(Job.created_at >= cutoff_date).count()
        
        total_companies = db.query(Company).count()
        new_companies = db.query(Company).filter(Company.created_at >= cutoff_date).count()
        
        total_users = db.query(UserProfile).count()
        active_users = db.query(UserProfile).filter(
            UserProfile.updated_at >= cutoff_date
        ).count()
        
        # Growth metrics
        prev_cutoff = cutoff_date - timedelta(days=days)
        prev_jobs = db.query(Job).filter(
            and_(Job.created_at >= prev_cutoff, Job.created_at < cutoff_date)
        ).count()
        
        job_growth_rate = ((new_jobs - prev_jobs) / prev_jobs * 100) if prev_jobs > 0 else 0
        
        return {
            "total_jobs": total_jobs,
            "active_jobs": active_jobs,
            "new_jobs_period": new_jobs,
            "job_growth_rate": round(job_growth_rate, 2),
            "total_companies": total_companies,
            "new_companies_period": new_companies,
            "total_users": total_users,
            "active_users_period": active_users,
            "job_activation_rate": round((active_jobs / total_jobs * 100), 2) if total_jobs > 0 else 0
        }
    
    def analyze_user_engagement(self, db: Session, days: int) -> Dict:
        """Analyze user engagement patterns"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # User activity metrics
        users_with_profiles = db.query(UserProfile).filter(
            UserProfile.skills.isnot(None)
        ).count()
        
        users_with_matches = db.query(Match.user_id).distinct().count()
        
        users_with_applications = db.query(JobApplication.user_id).distinct().count()
        
        # Match engagement
        total_matches = db.query(Match).filter(Match.created_at >= cutoff_date).count()
        high_score_matches = db.query(Match).filter(
            and_(Match.created_at >= cutoff_date, Match.overall_score >= 0.8)
        ).count()
        
        # Application conversion
        applications = db.query(JobApplication).filter(
            JobApplication.applied_date >= cutoff_date
        ).count()
        
        conversion_rate = (applications / total_matches * 100) if total_matches > 0 else 0
        
        return {
            "users_with_complete_profiles": users_with_profiles,
            "users_with_matches": users_with_matches,
            "users_with_applications": users_with_applications,
            "total_matches_generated": total_matches,
            "high_quality_matches": high_score_matches,
            "applications_submitted": applications,
            "match_to_application_rate": round(conversion_rate, 2),
            "high_quality_match_rate": round((high_score_matches / total_matches * 100), 2) if total_matches > 0 else 0
        }
    
    def analyze_job_performance(self, db: Session, days: int) -> Dict:
        """Analyze job posting performance"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Job source performance
        source_performance = db.query(
            Job.source,
            func.count(Job.id).label('job_count'),
            func.avg(Job.job_score).label('avg_score')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(Job.source).all()
        
        source_stats = {}
        for source, count, avg_score in source_performance:
            source_stats[source or 'unknown'] = {
                'job_count': count,
                'avg_quality_score': round(float(avg_score or 0), 3)
            }
        
        # Most matched jobs
        top_matched_jobs = db.query(
            Job.title,
            Job.company_id,
            func.count(Match.id).label('match_count')
        ).join(Match).filter(
            Match.created_at >= cutoff_date
        ).group_by(Job.id, Job.title, Job.company_id).order_by(
            func.count(Match.id).desc()
        ).limit(10).all()
        
        popular_jobs = []
        for title, company_id, match_count in top_matched_jobs:
            company = db.query(Company).filter(Company.id == company_id).first()
            popular_jobs.append({
                'job_title': title,
                'company_name': company.name if company else 'Unknown',
                'match_count': match_count
            })
        
        # Job posting trends by day
        daily_posts = db.query(
            func.date(Job.created_at).label('date'),
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(func.date(Job.created_at)).all()
        
        daily_trends = {str(date): count for date, count in daily_posts}
        
        return {
            "job_source_performance": source_stats,
            "most_popular_jobs": popular_jobs,
            "daily_posting_trends": daily_trends,
            "avg_jobs_per_day": round(sum(daily_trends.values()) / len(daily_trends), 2) if daily_trends else 0
        }
    
    def analyze_company_performance(self, db: Session, days: int) -> Dict:
        """Analyze company hiring performance"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Top hiring companies
        top_hiring = db.query(
            Company.name,
            Company.company_size,
            func.count(Job.id).label('jobs_posted')
        ).join(Job).filter(
            Job.created_at >= cutoff_date
        ).group_by(Company.id, Company.name, Company.company_size).order_by(
            func.count(Job.id).desc()
        ).limit(15).all()
        
        hiring_leaders = []
        for name, size, job_count in top_hiring:
            hiring_leaders.append({
                'company_name': name,
                'company_size': size,
                'jobs_posted': job_count
            })
        
        # Company size distribution
        size_distribution = db.query(
            Company.company_size,
            func.count(Company.id).label('company_count'),
            func.count(Job.id).label('total_jobs')
        ).outerjoin(Job).group_by(Company.company_size).all()
        
        size_stats = {}
        for size, company_count, job_count in size_distribution:
            size_stats[size or 'unknown'] = {
                'company_count': company_count,
                'total_jobs': job_count or 0,
                'avg_jobs_per_company': round((job_count or 0) / company_count, 2) if company_count > 0 else 0
            }
        
        # Industry analysis
        industry_stats = db.query(
            Company.industry,
            func.count(Company.id).label('company_count'),
            func.count(Job.id).label('job_count')
        ).outerjoin(Job).filter(
            Company.industry.isnot(None)
        ).group_by(Company.industry).order_by(
            func.count(Job.id).desc()
        ).limit(10).all()
        
        industry_breakdown = {}
        for industry, company_count, job_count in industry_stats:
            industry_breakdown[industry] = {
                'companies': company_count,
                'jobs': job_count or 0
            }
        
        return {
            "top_hiring_companies": hiring_leaders,
            "company_size_distribution": size_stats,
            "industry_breakdown": industry_breakdown
        }
    
    def analyze_matching_effectiveness(self, db: Session, days: int) -> Dict:
        """Analyze job matching algorithm effectiveness"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Match score distribution
        matches = db.query(Match.overall_score).filter(
            Match.created_at >= cutoff_date
        ).all()
        
        if not matches:
            return {"message": "No matches found in the specified period"}
        
        scores = [match.overall_score for match in matches]
        
        # Score buckets
        score_buckets = {
            "excellent (90-100%)": len([s for s in scores if s >= 0.9]),
            "very_good (80-89%)": len([s for s in scores if 0.8 <= s < 0.9]),
            "good (70-79%)": len([s for s in scores if 0.7 <= s < 0.8]),
            "fair (60-69%)": len([s for s in scores if 0.6 <= s < 0.7]),
            "poor (<60%)": len([s for s in scores if s < 0.6])
        }
        
        # Component score analysis
        component_scores = db.query(
            func.avg(Match.skill_score).label('avg_skill'),
            func.avg(Match.experience_score).label('avg_experience'),
            func.avg(Match.location_score).label('avg_location'),
            func.avg(Match.salary_score).label('avg_salary')
        ).filter(Match.created_at >= cutoff_date).first()
        
        component_analysis = {
            "skill_matching": round(float(component_scores.avg_skill or 0), 3),
            "experience_matching": round(float(component_scores.avg_experience or 0), 3),
            "location_matching": round(float(component_scores.avg_location or 0), 3),
            "salary_matching": round(float(component_scores.avg_salary or 0), 3)
        }
        
        # Application success rate by match score
        applications_by_score = db.query(
            Match.overall_score,
            JobApplication.id
        ).outerjoin(JobApplication, and_(
            Match.user_id == JobApplication.user_id,
            Match.job_id == JobApplication.job_id
        )).filter(Match.created_at >= cutoff_date).all()
        
        high_score_applications = len([
            app for score, app in applications_by_score 
            if score >= 0.8 and app is not None
        ])
        high_score_matches = len([score for score, _ in applications_by_score if score >= 0.8])
        
        high_score_conversion = (high_score_applications / high_score_matches * 100) if high_score_matches > 0 else 0
        
        return {
            "total_matches_analyzed": len(matches),
            "average_match_score": round(sum(scores) / len(scores), 3),
            "match_score_distribution": score_buckets,
            "component_effectiveness": component_analysis,
            "high_score_conversion_rate": round(high_score_conversion, 2)
        }
    
    def generate_recommendations(self, db: Session, days: int) -> Dict:
        """Generate actionable recommendations based on analytics"""
        recommendations = {
            "platform_improvements": [],
            "user_engagement": [],
            "job_quality": [],
            "matching_algorithm": []
        }
        
        # Analyze metrics to generate recommendations
        metrics = self.get_platform_metrics(db, days)
        engagement = self.analyze_user_engagement(db, days)
        matching = self.analyze_matching_effectiveness(db, days)
        
        # Platform recommendations
        if metrics["job_growth_rate"] < 10:
            recommendations["platform_improvements"].append(
                "Job growth rate is low. Consider expanding job aggregation sources."
            )
        
        if metrics["job_activation_rate"] < 80:
            recommendations["platform_improvements"].append(
                "Many jobs are inactive. Implement better job validation and cleanup."
            )
        
        # User engagement recommendations
        if engagement["match_to_application_rate"] < 5:
            recommendations["user_engagement"].append(
                "Low application conversion rate. Improve job presentation and application flow."
            )
        
        if engagement["high_quality_match_rate"] < 30:
            recommendations["user_engagement"].append(
                "Few high-quality matches. Enhance user profile completion and matching algorithm."
            )
        
        # Job quality recommendations
        job_perf = self.analyze_job_performance(db, days)
        if job_perf.get("avg_jobs_per_day", 0) < 10:
            recommendations["job_quality"].append(
                "Low daily job posting volume. Increase scraping frequency and add more sources."
            )
        
        # Matching algorithm recommendations
        if isinstance(matching, dict) and "component_effectiveness" in matching:
            components = matching["component_effectiveness"]
            
            if components["skill_matching"] < 0.7:
                recommendations["matching_algorithm"].append(
                    "Skill matching effectiveness is low. Improve skill extraction and normalization."
                )
            
            if components["location_matching"] < 0.6:
                recommendations["matching_algorithm"].append(
                    "Location matching needs improvement. Better location parsing and remote work detection."
                )
        
        return recommendations
    
    def get_user_analytics_dashboard(self, user_id: int) -> Dict:
        """Get personalized analytics dashboard for a user"""
        db = SessionLocal()
        try:
            user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
            if not user:
                return {}
            
            # User's match history
            matches = db.query(Match).filter(Match.user_id == user_id).all()
            
            # User's applications
            applications = db.query(JobApplication).filter(
                JobApplication.user_id == user_id
            ).all()
            
            # Match score trends (last 30 days)
            recent_matches = [m for m in matches if m.created_at >= datetime.utcnow() - timedelta(days=30)]
            
            dashboard = {
                "user_profile": {
                    "name": user.name,
                    "skills_count": len(user.skills.split(',')) if user.skills else 0,
                    "profile_completeness": self.calculate_profile_completeness(user)
                },
                "matching_stats": {
                    "total_matches": len(matches),
                    "recent_matches": len(recent_matches),
                    "average_match_score": round(sum(m.overall_score for m in matches) / len(matches), 3) if matches else 0,
                    "best_match_score": max(m.overall_score for m in matches) if matches else 0
                },
                "application_stats": {
                    "total_applications": len(applications),
                    "recent_applications": len([a for a in applications if a.applied_date >= datetime.utcnow() - timedelta(days=30)]),
                    "application_success_rate": self.calculate_application_success_rate(applications)
                },
                "personalized_insights": market_analyzer.get_personalized_market_insights(user_id)
            }
            
            return dashboard
            
        finally:
            db.close()
    
    def calculate_profile_completeness(self, user: UserProfile) -> float:
        """Calculate user profile completeness percentage"""
        fields = [
            user.name, user.email, user.skills, user.experience,
            user.education, user.preferred_locations, user.preferred_salary_min
        ]
        
        completed_fields = sum(1 for field in fields if field is not None and str(field).strip())
        return round((completed_fields / len(fields)) * 100, 1)
    
    def calculate_application_success_rate(self, applications: List[JobApplication]) -> float:
        """Calculate application success rate"""
        if not applications:
            return 0.0
        
        successful_apps = len([app for app in applications if app.status in ['offered', 'hired']])
        return round((successful_apps / len(applications)) * 100, 2)
    
    def export_analytics_data(self, format: str = 'json', days: int = 30) -> str:
        """Export analytics data in specified format"""
        report = self.generate_comprehensive_report(days)
        
        if format.lower() == 'json':
            return json.dumps(report, indent=2, default=str)
        elif format.lower() == 'csv':
            # Convert to CSV format (simplified)
            csv_data = "Metric,Value\n"
            
            # Flatten the report for CSV
            def flatten_dict(d, parent_key='', sep='_'):
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    else:
                        items.append((new_key, v))
                return dict(items)
            
            flat_report = flatten_dict(report)
            for key, value in flat_report.items():
                csv_data += f"{key},{value}\n"
            
            return csv_data
        else:
            return json.dumps(report, indent=2, default=str)

# Global analytics engine instance
analytics_engine = AnalyticsEngine()
