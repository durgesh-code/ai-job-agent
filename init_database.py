#!/usr/bin/env python3
"""
Database initialization script for AI Job Agent
Run this script to create all database tables
"""

import sys
import os
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Initialize the database with all required tables"""
    print("🔧 Initializing AI Job Agent Database...")
    
    # Ensure data directory exists
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)
    
    try:
        # Import database components
        from src.db import init_db, engine
        from src.models import (
            Company, Job, Run, Match, UserProfile, JobApplication,
            JobMarketTrend, SalaryBenchmark, Notification
        )
        
        print("📊 Creating database tables...")
        
        # Initialize all tables
        init_db()
        
        print("✅ Database initialization completed successfully!")
        print(f"📁 Database location: {data_dir / 'db.sqlite'}")
        
        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"📋 Created {len(tables)} tables:")
        for table in sorted(tables):
            print(f"   • {table}")
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
