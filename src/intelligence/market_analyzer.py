# src/intelligence/market_analyzer.py
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from collections import defaultdict

from ..db import SessionLocal
from ..models import Job, Company, Match, UserProfile
from ..config import config

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    """Market intelligence and trend analysis"""
    
    def __init__(self):
        self.intelligence_config = config.intelligence_config
    
    def analyze_job_market_trends(self, days: int = 30) -> Dict:
        """Analyze job market trends over specified period"""
        db = SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Job posting trends
            job_trends = self.analyze_job_posting_trends(db, cutoff_date)
            
            # Salary trends
            salary_trends = self.analyze_salary_trends(db, cutoff_date)
            
            # Skills demand
            skills_demand = self.analyze_skills_demand(db, cutoff_date)
            
            # Location trends
            location_trends = self.analyze_location_trends(db, cutoff_date)
            
            # Remote work trends
            remote_trends = self.analyze_remote_work_trends(db, cutoff_date)
            
            # Company hiring patterns
            company_trends = self.analyze_company_hiring_patterns(db, cutoff_date)
            
            return {
                "analysis_period_days": days,
                "generated_at": datetime.utcnow().isoformat(),
                "job_posting_trends": job_trends,
                "salary_trends": salary_trends,
                "skills_demand": skills_demand,
                "location_trends": location_trends,
                "remote_work_trends": remote_trends,
                "company_hiring_patterns": company_trends
            }
            
        finally:
            db.close()
    
    def analyze_job_posting_trends(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze job posting volume and trends"""
        # Total jobs posted in period
        total_jobs = db.query(Job).filter(Job.created_at >= cutoff_date).count()
        
        # Jobs by experience level
        exp_level_query = db.query(
            Job.experience_level,
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(Job.experience_level).all()
        
        exp_level_distribution = {level: count for level, count in exp_level_query}
        
        # Daily posting volume
        daily_posts = db.query(
            func.date(Job.created_at).label('date'),
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(func.date(Job.created_at)).all()
        
        daily_volume = {str(date): count for date, count in daily_posts}
        
        # Growth rate calculation
        mid_point = cutoff_date + (datetime.utcnow() - cutoff_date) / 2
        first_half = db.query(Job).filter(
            and_(Job.created_at >= cutoff_date, Job.created_at < mid_point)
        ).count()
        second_half = db.query(Job).filter(Job.created_at >= mid_point).count()
        
        growth_rate = ((second_half - first_half) / first_half * 100) if first_half > 0 else 0
        
        return {
            "total_jobs_posted": total_jobs,
            "experience_level_distribution": exp_level_distribution,
            "daily_posting_volume": daily_volume,
            "growth_rate_percentage": round(growth_rate, 2),
            "average_daily_posts": round(total_jobs / max((datetime.utcnow() - cutoff_date).days, 1), 2)
        }
    
    def analyze_salary_trends(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze salary trends and ranges"""
        # Jobs with salary information
        salary_jobs = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                or_(Job.salary_min.isnot(None), Job.salary_max.isnot(None))
            )
        ).all()
        
        if not salary_jobs:
            return {"message": "Insufficient salary data"}
        
        # Calculate salary statistics
        min_salaries = [job.salary_min for job in salary_jobs if job.salary_min]
        max_salaries = [job.salary_max for job in salary_jobs if job.salary_max]
        
        salary_stats = {}
        
        if min_salaries:
            salary_stats["min_salary_stats"] = {
                "average": round(sum(min_salaries) / len(min_salaries)),
                "median": sorted(min_salaries)[len(min_salaries) // 2],
                "range": [min(min_salaries), max(min_salaries)]
            }
        
        if max_salaries:
            salary_stats["max_salary_stats"] = {
                "average": round(sum(max_salaries) / len(max_salaries)),
                "median": sorted(max_salaries)[len(max_salaries) // 2],
                "range": [min(max_salaries), max(max_salaries)]
            }
        
        # Salary by experience level
        salary_by_exp = defaultdict(list)
        for job in salary_jobs:
            if job.experience_level and job.salary_min:
                salary_by_exp[job.experience_level].append(job.salary_min)
        
        exp_salary_stats = {}
        for level, salaries in salary_by_exp.items():
            if salaries:
                exp_salary_stats[level] = {
                    "average": round(sum(salaries) / len(salaries)),
                    "count": len(salaries)
                }
        
        return {
            "jobs_with_salary_info": len(salary_jobs),
            "salary_statistics": salary_stats,
            "salary_by_experience_level": exp_salary_stats
        }
    
    def analyze_skills_demand(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze most in-demand skills"""
        jobs_with_skills = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.required_skills.isnot(None)
            )
        ).all()
        
        skill_counts = defaultdict(int)
        skill_salary_map = defaultdict(list)
        
        for job in jobs_with_skills:
            skills = [skill.strip().lower() for skill in job.required_skills.split(',')]
            for skill in skills:
                if skill:  # Skip empty skills
                    skill_counts[skill] += 1
                    if job.salary_min:
                        skill_salary_map[skill].append(job.salary_min)
        
        # Top 20 most demanded skills
        top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Skills with salary data
        skills_with_salary = {}
        for skill, salaries in skill_salary_map.items():
            if len(salaries) >= 3:  # At least 3 data points
                skills_with_salary[skill] = {
                    "average_salary": round(sum(salaries) / len(salaries)),
                    "job_count": len(salaries)
                }
        
        # Trending skills (skills appearing more in recent jobs)
        mid_point = cutoff_date + (datetime.utcnow() - cutoff_date) / 2
        recent_jobs = [job for job in jobs_with_skills if job.created_at >= mid_point]
        
        recent_skill_counts = defaultdict(int)
        for job in recent_jobs:
            skills = [skill.strip().lower() for skill in job.required_skills.split(',')]
            for skill in skills:
                if skill:
                    recent_skill_counts[skill] += 1
        
        # Calculate trend score (recent frequency / total frequency)
        trending_skills = []
        for skill, total_count in skill_counts.items():
            recent_count = recent_skill_counts.get(skill, 0)
            if total_count >= 5:  # Only consider skills with reasonable volume
                trend_score = recent_count / total_count if total_count > 0 else 0
                trending_skills.append((skill, trend_score, total_count))
        
        trending_skills.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "total_jobs_analyzed": len(jobs_with_skills),
            "top_skills_demand": dict(top_skills),
            "skills_salary_analysis": skills_with_salary,
            "trending_skills": [
                {"skill": skill, "trend_score": round(score, 3), "total_mentions": count}
                for skill, score, count in trending_skills[:10]
            ]
        }
    
    def analyze_location_trends(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze job location trends"""
        location_query = db.query(
            Job.location,
            func.count(Job.id).label('count')
        ).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.location.isnot(None)
            )
        ).group_by(Job.location).order_by(func.count(Job.id).desc()).all()
        
        location_distribution = {loc: count for loc, count in location_query[:20]}
        
        # City-level analysis (extract cities from locations)
        city_counts = defaultdict(int)
        for location, count in location_query:
            # Simple city extraction (first part before comma)
            city = location.split(',')[0].strip() if location else ''
            if city:
                city_counts[city] += count
        
        top_cities = dict(sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:15])
        
        return {
            "top_job_locations": location_distribution,
            "top_cities": top_cities,
            "total_locations": len(location_distribution)
        }
    
    def analyze_remote_work_trends(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze remote work adoption trends"""
        remote_query = db.query(
            Job.remote_option,
            func.count(Job.id).label('count')
        ).filter(
            Job.created_at >= cutoff_date
        ).group_by(Job.remote_option).all()
        
        remote_distribution = {option or 'not_specified': count for option, count in remote_query}
        total_jobs = sum(remote_distribution.values())
        
        # Calculate percentages
        remote_percentages = {}
        for option, count in remote_distribution.items():
            remote_percentages[option] = round((count / total_jobs * 100), 2) if total_jobs > 0 else 0
        
        # Trend analysis (compare first half vs second half of period)
        mid_point = cutoff_date + (datetime.utcnow() - cutoff_date) / 2
        
        first_half_remote = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.created_at < mid_point,
                Job.remote_option == 'remote'
            )
        ).count()
        
        first_half_total = db.query(Job).filter(
            and_(Job.created_at >= cutoff_date, Job.created_at < mid_point)
        ).count()
        
        second_half_remote = db.query(Job).filter(
            and_(Job.created_at >= mid_point, Job.remote_option == 'remote')
        ).count()
        
        second_half_total = db.query(Job).filter(Job.created_at >= mid_point).count()
        
        first_half_percentage = (first_half_remote / first_half_total * 100) if first_half_total > 0 else 0
        second_half_percentage = (second_half_remote / second_half_total * 100) if second_half_total > 0 else 0
        
        remote_trend = second_half_percentage - first_half_percentage
        
        return {
            "remote_work_distribution": remote_distribution,
            "remote_work_percentages": remote_percentages,
            "remote_trend_change": round(remote_trend, 2),
            "trend_direction": "increasing" if remote_trend > 1 else "decreasing" if remote_trend < -1 else "stable"
        }
    
    def analyze_company_hiring_patterns(self, db: Session, cutoff_date: datetime) -> Dict:
        """Analyze which companies are hiring most actively"""
        company_hiring = db.query(
            Company.name,
            Company.company_size,
            func.count(Job.id).label('jobs_posted')
        ).join(Job).filter(
            Job.created_at >= cutoff_date
        ).group_by(Company.id, Company.name, Company.company_size).order_by(
            func.count(Job.id).desc()
        ).limit(20).all()
        
        top_hiring_companies = [
            {
                "company": name,
                "company_size": size,
                "jobs_posted": count
            }
            for name, size, count in company_hiring
        ]
        
        # Hiring by company size
        size_hiring = db.query(
            Company.company_size,
            func.count(Job.id).label('jobs_posted')
        ).join(Job).filter(
            Job.created_at >= cutoff_date
        ).group_by(Company.company_size).all()
        
        hiring_by_size = {size or 'unknown': count for size, count in size_hiring}
        
        return {
            "top_hiring_companies": top_hiring_companies,
            "hiring_by_company_size": hiring_by_size
        }
    
    def get_personalized_market_insights(self, user_id: int) -> Dict:
        """Get personalized market insights for a user"""
        db = SessionLocal()
        try:
            user = db.query(UserProfile).filter(UserProfile.id == user_id).first()
            if not user:
                return {}
            
            insights = {}
            
            # Skills market analysis
            if user.skills:
                user_skills = [skill.strip().lower() for skill in user.skills.split(',')]
                skills_analysis = self.analyze_user_skills_market(db, user_skills)
                insights['skills_market_analysis'] = skills_analysis
            
            # Location market analysis
            if user.preferred_locations:
                locations = [loc.strip() for loc in user.preferred_locations.split(',')]
                location_analysis = self.analyze_location_market(db, locations)
                insights['location_market_analysis'] = location_analysis
            
            # Experience level market
            if user.years_experience:
                exp_level = self.get_experience_level(user.years_experience)
                exp_analysis = self.analyze_experience_level_market(db, exp_level)
                insights['experience_level_analysis'] = exp_analysis
            
            # Salary benchmarking
            if user.preferred_salary_min:
                salary_benchmark = self.analyze_salary_benchmark(db, user)
                insights['salary_benchmark'] = salary_benchmark
            
            return insights
            
        finally:
            db.close()
    
    def analyze_user_skills_market(self, db: Session, user_skills: List[str]) -> Dict:
        """Analyze market demand for user's skills"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        skill_demand = {}
        for skill in user_skills:
            # Count jobs requiring this skill
            job_count = db.query(Job).filter(
                and_(
                    Job.created_at >= cutoff_date,
                    Job.required_skills.ilike(f'%{skill}%')
                )
            ).count()
            
            if job_count > 0:
                skill_demand[skill] = job_count
        
        # Sort by demand
        sorted_skills = sorted(skill_demand.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "skills_in_demand": dict(sorted_skills),
            "total_relevant_jobs": sum(skill_demand.values()),
            "top_skill": sorted_skills[0] if sorted_skills else None
        }
    
    def analyze_location_market(self, db: Session, preferred_locations: List[str]) -> Dict:
        """Analyze job market in user's preferred locations"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        location_jobs = {}
        for location in preferred_locations:
            job_count = db.query(Job).filter(
                and_(
                    Job.created_at >= cutoff_date,
                    Job.location.ilike(f'%{location}%')
                )
            ).count()
            
            if job_count > 0:
                location_jobs[location] = job_count
        
        return {
            "jobs_by_preferred_location": location_jobs,
            "total_jobs_in_preferred_locations": sum(location_jobs.values())
        }
    
    def get_experience_level(self, years: int) -> str:
        """Convert years of experience to experience level"""
        if years <= 2:
            return 'entry'
        elif years <= 5:
            return 'mid'
        elif years <= 10:
            return 'senior'
        else:
            return 'lead'
    
    def analyze_experience_level_market(self, db: Session, exp_level: str) -> Dict:
        """Analyze job market for specific experience level"""
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        level_jobs = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.experience_level == exp_level
            )
        ).count()
        
        total_jobs = db.query(Job).filter(Job.created_at >= cutoff_date).count()
        
        market_share = (level_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        return {
            "experience_level": exp_level,
            "available_jobs": level_jobs,
            "market_share_percentage": round(market_share, 2)
        }
    
    def analyze_salary_benchmark(self, db: Session, user: UserProfile) -> Dict:
        """Analyze salary benchmark for user profile"""
        cutoff_date = datetime.utcnow() - timedelta(days=90)  # Longer period for salary data
        
        # Find similar jobs based on user profile
        query = db.query(Job).filter(
            and_(
                Job.created_at >= cutoff_date,
                Job.salary_min.isnot(None)
            )
        )
        
        # Filter by experience level if available
        if user.years_experience:
            exp_level = self.get_experience_level(user.years_experience)
            query = query.filter(Job.experience_level == exp_level)
        
        # Filter by skills if available
        if user.skills:
            user_skills = user.skills.split(',')[:3]  # Top 3 skills
            for skill in user_skills:
                query = query.filter(Job.required_skills.ilike(f'%{skill.strip()}%'))
        
        similar_jobs = query.all()
        
        if not similar_jobs:
            return {"message": "Insufficient data for salary benchmark"}
        
        salaries = [job.salary_min for job in similar_jobs if job.salary_min]
        
        if not salaries:
            return {"message": "No salary data available for similar positions"}
        
        benchmark = {
            "similar_jobs_analyzed": len(similar_jobs),
            "salary_range": {
                "min": min(salaries),
                "max": max(salaries),
                "average": round(sum(salaries) / len(salaries)),
                "median": sorted(salaries)[len(salaries) // 2]
            }
        }
        
        # Compare with user's preferred salary
        if user.preferred_salary_min:
            avg_market_salary = benchmark["salary_range"]["average"]
            difference = user.preferred_salary_min - avg_market_salary
            percentage_diff = (difference / avg_market_salary * 100) if avg_market_salary > 0 else 0
            
            benchmark["user_salary_comparison"] = {
                "user_preferred": user.preferred_salary_min,
                "market_average": avg_market_salary,
                "difference": difference,
                "percentage_difference": round(percentage_diff, 2),
                "assessment": "above_market" if percentage_diff > 10 else "below_market" if percentage_diff < -10 else "market_rate"
            }
        
        return benchmark

# Global market analyzer instance
market_analyzer = MarketAnalyzer()
