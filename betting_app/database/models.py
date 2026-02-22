from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Fixture(Base):
    __tablename__ = "fixtures"

    id = Column(String, primary_key=True, default=generate_uuid)
    fixture_name = Column(String) # For racing or general description
    sport = Column(String, index=True)
    league = Column(String, index=True)
    home_team = Column(String, index=True)
    away_team = Column(String, index=True)
    start_time = Column(DateTime(timezone=True))
    status = Column(String, default="scheduled") # scheduled, live, finished, postponed
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    result_settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    odds = relationship("Odds", back_populates="fixture")
    sentiment = relationship("Sentiment", back_populates="fixture")
    predictions = relationship("Prediction", back_populates="fixture")
    snapshots = relationship("PredictionSnapshot", back_populates="fixture")

class Odds(Base):
    __tablename__ = "odds"

    id = Column(String, primary_key=True, default=generate_uuid)
    fixture_id = Column(String, ForeignKey("fixtures.id"))
    bookmaker = Column(String, index=True) # e.g., "SportsBet", "TAB", "Pinnacle"
    market_type = Column(String) # e.g., "h2h", "spreads", "totals"
    selection = Column(String) # e.g., "Home", "Away", "Over", "Under"
    price = Column(Float)
    point = Column(Float, nullable=True) # For spreads (-3.5) and totals (54.5)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    fixture = relationship("Fixture", back_populates="odds")

class Sentiment(Base):
    __tablename__ = "sentiment"

    id = Column(String, primary_key=True, default=generate_uuid)
    fixture_id = Column(String, ForeignKey("fixtures.id"))
    source = Column(String) # e.g., "Twitter", "Reddit"
    content = Column(String)
    sentiment_score = Column(Float) # -1.0 to 1.0
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    fixture = relationship("Fixture", back_populates="sentiment")

class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(String, primary_key=True, default=generate_uuid)
    fixture_id = Column(String, ForeignKey("fixtures.id"))
    market_type = Column(String)
    selection = Column(String)
    model_probability = Column(Float)
    value_score = Column(Float) # (Prob * Odds) - 1
    confidence_level = Column(String) # "High", "Medium", "Low"
    reasoning = Column(String) # Explanation for the suggestion
    is_recommended = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fixture = relationship("Fixture", back_populates="predictions")

class PredictionSnapshot(Base):
    __tablename__ = "prediction_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    fixture_id = Column(String, ForeignKey("fixtures.id"))
    sport = Column(String, index=True)
    league = Column(String)
    home_team = Column(String)
    away_team = Column(String)
    start_time = Column(DateTime(timezone=True))
    market_type = Column(String)
    selection = Column(String)
    model_probability = Column(Float)
    value_score = Column(Float)
    confidence_level = Column(String)
    is_recommended = Column(Boolean, default=False)
    best_odds = Column(Float, nullable=True)
    point = Column(Float, nullable=True)
    outcome = Column(String, nullable=True)  # "correct", "incorrect", "push", None
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    fixture = relationship("Fixture", back_populates="snapshots")
