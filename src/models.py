# src/models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, JSON, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True)
    homepage = Column(String)
    careers_url = Column(String, nullable=True)
    meta_info = Column(Text, nullable=True)
    industry = Column(String, nullable=True)
    
    # Enhanced company data
    industry = Column(String, nullable=True)
    company_size = Column(String, nullable=True)  # startup, small, medium, large, enterprise
    funding_stage = Column(String, nullable=True)  # seed, series_a, series_b, etc.
    location = Column(String, nullable=True)
    remote_policy = Column(String, nullable=True)  # remote, hybrid, onsite
    glassdoor_rating = Column(Float, nullable=True)
    glassdoor_url = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    tech_stack = Column(JSON, default=list)  # Technologies used
    company_score = Column(Float, default=0.0)  # Our computed score
    last_updated = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("Job", back_populates="company")
    
    __table_args__ = (
        Index('idx_company_score', 'company_score'),
        Index('idx_company_size', 'company_size'),
        Index('idx_company_location', 'location'),
    )

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"))
    external_id = Column(String, index=True)  # e.g. vendor id or hash
    title = Column(String)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    apply_url = Column(String, nullable=True)
    posted_date = Column(DateTime, nullable=True)
    raw_hash = Column(String, nullable=True)
    meta_info = Column(Text, nullable=True)
    
    # Enhanced job data
    job_type = Column(String, nullable=True)  # full-time, part-time, contract, internship
    experience_level = Column(String, nullable=True)  # entry, junior, mid, senior, lead, principal
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    salary_currency = Column(String, default='USD')
    remote_option = Column(String, nullable=True)  # remote, hybrid, onsite
    required_skills = Column(JSON, default=list)
    preferred_skills = Column(JSON, default=list)
    benefits = Column(JSON, default=list)
    
    # Scoring and matching
    job_score = Column(Float, default=0.0)  # Overall job attractiveness
    freshness_score = Column(Float, default=1.0)  # How recent the job is
    competition_level = Column(String, nullable=True)  # low, medium, high
    
    # Status tracking
    is_active = Column(Boolean, default=True)
    source = Column(String, default='company_website')  # company_website, linkedin, indeed, etc.
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("JobApplication", back_populates="job")
    
    __table_args__ = (
        Index('idx_job_score', 'job_score'),
        Index('idx_job_posted_date', 'posted_date'),
        Index('idx_job_experience_level', 'experience_level'),
        Index('idx_job_location', 'location'),
        Index('idx_job_active', 'is_active'),
    )

class Run(Base):
    __tablename__ = "runs"
    id = Column(Integer, primary_key=True)
    type = Column(String)  # company_discovery, job_scraping, matching, analytics
    status = Column(String, default='running')  # running, completed, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    stats = Column(JSON, default={})
    error_message = Column(Text, nullable=True)

# User Profile Management
class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    # Resume data
    resume_text = Column(Text, nullable=True)
    skills = Column(JSON, default=list)
    experience_years = Column(Integer, nullable=True)
    current_title = Column(String, nullable=True)
    preferred_roles = Column(JSON, default=list)
    
    # Preferences
    preferred_locations = Column(JSON, default=list)
    preferred_remote = Column(String, nullable=True)  # remote, hybrid, onsite, any
    preferred_company_size = Column(JSON, default=list)
    preferred_salary_min = Column(Integer, nullable=True)
    preferred_salary_max = Column(Integer, nullable=True)
    
    # Career goals
    career_level = Column(String, nullable=True)  # entry, junior, mid, senior, lead, principal
    target_industries = Column(JSON, default=list)
    learning_goals = Column(JSON, default=list)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = relationship("JobApplication", back_populates="user")
    matches = relationship("Match", back_populates="user")

# Job Applications Tracking
class JobApplication(Base):
    __tablename__ = "job_applications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    
    status = Column(String, default='interested')  # interested, applied, interviewing, rejected, offered, accepted
    applied_date = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Interview tracking
    interview_rounds = Column(JSON, default=list)
    feedback = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("UserProfile", back_populates="applications")
    job = relationship("Job", back_populates="applications")

# Enhanced Matching System
class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    
    # Scoring breakdown
    overall_score = Column(Float)
    semantic_score = Column(Float)
    skill_match_score = Column(Float)
    experience_match_score = Column(Float)
    location_match_score = Column(Float)
    salary_match_score = Column(Float)
    company_match_score = Column(Float)
    
    # Matching details
    matched_skills = Column(JSON, default=list)
    missing_skills = Column(JSON, default=list)
    reasons = Column(JSON, default=list)
    
    # User interaction
    is_viewed = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)
    user_rating = Column(Integer, nullable=True)  # 1-5 stars
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("UserProfile", back_populates="matches")
    job = relationship("Job")
    
    __table_args__ = (
        Index('idx_match_score', 'overall_score'),
        Index('idx_match_user_job', 'user_id', 'job_id'),
    )

# Job Market Analytics
class JobMarketTrend(Base):
    __tablename__ = "job_market_trends"
    id = Column(Integer, primary_key=True)
    
    skill = Column(String, index=True)
    location = Column(String, nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    
    # Trend data
    job_count = Column(Integer, default=0)
    avg_salary = Column(Float, nullable=True)
    demand_level = Column(String, nullable=True)  # low, medium, high
    growth_rate = Column(Float, nullable=True)  # percentage
    
    __table_args__ = (
        Index('idx_trend_skill_date', 'skill', 'date'),
    )

# Salary Benchmarks
class SalaryBenchmark(Base):
    __tablename__ = "salary_benchmarks"
    id = Column(Integer, primary_key=True)
    
    title = Column(String, index=True)
    location = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    salary_median = Column(Integer)
    currency = Column(String, default='USD')
    
    sample_size = Column(Integer, default=1)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_salary_title_location', 'title', 'location'),
    )

# Notification System
class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("user_profiles.id"))
    
    type = Column(String)  # new_match, job_alert, application_update, market_insight
    title = Column(String)
    message = Column(Text)
    data = Column(JSON, default=dict)  # Additional data for the notification
    
    is_read = Column(Boolean, default=False)
    is_sent = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
