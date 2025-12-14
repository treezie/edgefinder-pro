from database.db import SessionLocal
from database.models import Prediction, Odds, Fixture
db = SessionLocal()

# Delete all predictions
num_deleted = db.query(Prediction).delete()
db.commit()
print(f"Deleted {num_deleted} old predictions.")

# Delete all odds
num_deleted_odds = db.query(Odds).delete()
db.commit()
print(f"Deleted {num_deleted_odds} old odds.")

# Delete all fixtures
num_deleted_fixtures = db.query(Fixture).delete()
db.commit()
print(f"Deleted {num_deleted_fixtures} old fixtures.")
