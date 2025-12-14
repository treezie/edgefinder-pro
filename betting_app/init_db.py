from database.db import engine, Base
from database.models import Fixture, Odds, Sentiment, Prediction

def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

if __name__ == "__main__":
    init_db()
