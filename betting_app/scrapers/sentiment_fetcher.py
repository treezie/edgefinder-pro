import asyncio
from typing import Dict, Any

class SentimentFetcher:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    
    def __init__(self, sport: str):
        self.sport = sport
        self.analyzer = self.SentimentIntensityAnalyzer()

    async def analyze_sentiment(self, fixture_name: str, headlines: list = None) -> Dict[str, Any]:
        """
        Analyzes sentiment from real headlines using VADER.
        """
        score = 0.0
        volume = 0
        
        if headlines:
            volume = len(headlines)
            compound_scores = []
            for h in headlines:
                vs = self.analyzer.polarity_scores(h)
                compound_scores.append(vs['compound'])
            
            if compound_scores:
                score = sum(compound_scores) / len(compound_scores)
        
        return {
            "fixture": fixture_name,
            "sentiment_score": score,
            "volume": volume,
            "headlines": headlines or []
        }
