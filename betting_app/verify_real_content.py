from database.db import SessionLocal
from database.models import Prediction, Fixture
db = SessionLocal()
predictions = db.query(Prediction).join(Fixture).filter(Fixture.sport == "NFL").all()

print(f"Found {len(predictions)} NFL predictions.")
for p in predictions[:5]:
    print(f"Fixture: {p.fixture.fixture_name}")
    print(f"Selection: {p.selection}")
    print(f"Reasoning: {p.reasoning}")
    print("-" * 20)
