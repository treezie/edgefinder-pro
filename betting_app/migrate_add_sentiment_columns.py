#!/usr/bin/env python3
"""
Migration script to add 1-10 scoring columns to the sentiment table.
"""
from database.db import engine
from sqlalchemy import text


def migrate():
    columns = [
        ("sentiment_score_1_10", "INTEGER"),
        ("volume", "INTEGER"),
        ("confidence", "FLOAT"),
    ]

    with engine.connect() as conn:
        for col_name, col_type in columns:
            try:
                conn.execute(text(f"ALTER TABLE sentiment ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"  Added '{col_name}' column to sentiment table")
            except Exception as e:
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"  Column '{col_name}' already exists - skipping")
                else:
                    print(f"  Error adding '{col_name}': {e}")
                    raise

    print("Migration complete.")


if __name__ == "__main__":
    migrate()
