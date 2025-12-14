from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class BaseScraper(ABC):
    def __init__(self, sport: str):
        self.sport = sport

    @abstractmethod
    async def fetch_odds(self) -> List[Dict[str, Any]]:
        """
        Fetch odds from the source.
        Returns a list of dictionaries containing:
        - fixture_name
        - start_time
        - market_type
        - selection
        - price
        - bookmaker
        """
        pass

    def normalize_team_name(self, name: str) -> str:
        """
        Helper to normalize team names for matching across sources.
        """
        return name.strip().lower() # Placeholder for more complex logic
