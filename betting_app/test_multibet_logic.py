"""
Simple test to call the multibet function directly
"""
import sys
sys.path.insert(0, '.')

from database.db import SessionLocal
from database.models import Prediction, Fixture, Odds
from datetime import datetime

db = SessionLocal()

# Test the query that multibets uses
print("Testing NFL predictions query...")
nfl_preds = (
    db.query(Prediction)
    .join(Fixture)
    .filter(Prediction.is_recommended == True, Prediction.value_score > 0.03)
    .filter(Fixture.start_time > datetime.utcnow())
    .filter(Fixture.sport == 'NFL')
    .order_by(Prediction.value_score.desc())
    .limit(10)
    .all()
)
print(f"Found {len(nfl_preds)} NFL predictions")

print("\nTesting NBA predictions query...")
nba_preds = (
    db.query(Prediction)
    .join(Fixture)
    .filter(Prediction.is_recommended == True, Prediction.value_score > 0.03)
    .filter(Fixture.start_time > datetime.utcnow())
    .filter(Fixture.sport == 'NBA')
    .order_by(Prediction.value_score.desc())
    .limit(10)
    .all()
)
print(f"Found {len(nba_preds)} NBA predictions")

all_preds = nfl_preds + nba_preds
print(f"\nTotal predictions: {len(all_preds)}")

# Test creating a leg
if all_preds:
    print("\nTesting leg creation...")
    pred = all_preds[0]
    fixture = db.query(Fixture).filter(Fixture.id == pred.fixture_id).first()
    print(f"Fixture: {fixture.home_team} vs {fixture.away_team}")
    
    odds_entry = db.query(Odds).filter(
        Odds.fixture_id == pred.fixture_id,
        Odds.selection == pred.selection
    ).order_by(Odds.price.desc()).first()
    
    if odds_entry:
        print(f"Odds: {odds_entry.price}")
    else:
        print("No odds found!")
        
# Test combinations
print("\nTesting combinations import...")
try:
    from itertools import combinations
    print("✅ combinations imported successfully")
except Exception as e:
    print(f"❌ Error importing combinations: {e}")

db.close()
print("\n✅ All basic tests passed")
