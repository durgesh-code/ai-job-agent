# src/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./data/db.sqlite"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_db():
    from .models import (
        Company, Job, Run, Match, UserProfile, JobApplication, 
        JobMarketTrend, SalaryBenchmark, Notification
    )
    Base.metadata.create_all(bind=engine)
