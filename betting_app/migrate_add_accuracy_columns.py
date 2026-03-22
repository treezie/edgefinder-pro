#!/usr/bin/env python3
"""
Migration script to add accuracy-tracking columns to fixtures table
and create the prediction_snapshots table.
"""
from database.db import engine, Base
from database.models import PredictionSnapshot  # Ensure model is registered
from sqlalchemy import text

def migrate():
    # 1. Add columns to fixtures table
    columns = [
        ("home_score", "INTEGER"),
        ("away_score", "INTEGER"),
        ("result_settled_at", "TIMESTAMP"),
    ]

    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE fixtures ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"  Added '{col_name}' column to fixtures table")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  Column '{col_name}' already exists - skipping")
                else:
                    print(f"  Error adding '{col_name}': {e}")
                    raise

    # 2. Create prediction_snapshots table
    try:
        Base.metadata.create_all(bind=engine, tables=[PredictionSnapshot.__table__])
        print("  Created 'prediction_snapshots' table (or already exists)")
    except Exception as e:
        print(f"  Error creating prediction_snapshots table: {e}")
        raise

    print("Migration complete.")

if __name__ == "__main__":
    migrate()
