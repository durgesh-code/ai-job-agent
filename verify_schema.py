#!/usr/bin/env python3
"""
Verify database schema and check if user_id column exists in matches table
"""

import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from src.db import engine
from sqlalchemy import inspect, text

def main():
    """Verify the database schema"""
    print("🔍 Verifying database schema...")
    
    inspector = inspect(engine)
    
    # Check if matches table exists
    if 'matches' not in inspector.get_table_names():
        print("❌ matches table does not exist!")
        return
    
    # Get columns in matches table
    columns = inspector.get_columns('matches')
    column_names = [col['name'] for col in columns]
    
    print(f"📋 Columns in matches table: {column_names}")
    
    if 'user_id' in column_names:
        print("✅ user_id column exists in matches table")
    else:
        print("❌ user_id column is missing from matches table")
        
    # Test a simple query
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM matches"))
            count = result.scalar()
            print(f"📊 Current matches count: {count}")
    except Exception as e:
        print(f"❌ Error querying matches table: {e}")

if __name__ == "__main__":
    main()
