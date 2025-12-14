from database.db import SessionLocal
from database.models import Fixture
db = SessionLocal()
nfl_games = db.query(Fixture).filter(Fixture.sport == "NFL").all()
print(f"Found {len(nfl_games)} NFL games.")
for game in nfl_games[:5]:
    print(f"- {game.fixture_name} at {game.start_time}")
