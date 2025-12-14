"""
Script to remove duplicate predictions from the database.
Keeps the most recent prediction for each unique (fixture_id, market_type, selection) combination.
"""
from database.db import SessionLocal
from database.models import Prediction
from sqlalchemy import func
from collections import defaultdict

def remove_duplicates():
    db = SessionLocal()
    
    try:
        # Get all predictions
        all_predictions = db.query(Prediction).all()
        print(f"Total predictions before cleanup: {len(all_predictions)}")
        
        # Group by unique combination
        groups = defaultdict(list)
        for pred in all_predictions:
            key = (pred.fixture_id, pred.market_type, pred.selection)
            groups[key].append(pred)
        
        # Find and remove duplicates
        duplicates_removed = 0
        for key, preds in groups.items():
            if len(preds) > 1:
                # Sort by ID (assuming higher ID = more recent)
                preds.sort(key=lambda x: x.id, reverse=True)
                
                # Keep the first (most recent), delete the rest
                for pred in preds[1:]:
                    db.delete(pred)
                    duplicates_removed += 1
        
        db.commit()
        
        # Verify
        remaining = db.query(Prediction).count()
        print(f"Duplicates removed: {duplicates_removed}")
        print(f"Total predictions after cleanup: {remaining}")
        print(f"✅ Cleanup complete!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error during cleanup: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    remove_duplicates()
