#!/usr/bin/env python3
"""
Migration script to add point column to odds table
"""
from database.db import engine
from sqlalchemy import text

def migrate():
    print("Adding 'point' column to 'odds' table...")

    with engine.connect() as conn:
        try:
            # Try to add the column (will fail if it already exists)
            conn.execute(text("ALTER TABLE odds ADD COLUMN point FLOAT"))
            conn.commit()
            print("✓ Successfully added 'point' column to odds table")
        except Exception as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print("⚠ Column 'point' already exists - skipping")
            else:
                print(f"❌ Error: {e}")
                raise

if __name__ == "__main__":
    migrate()
