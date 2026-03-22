import asyncio
from typing import Dict, Any

class SentimentFetcher:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    
    def __init__(self, sport: str):
        self.sport = sport
        self.analyzer = self.SentimentIntensityAnalyzer()

    def _compound_to_1_10(self, compound: float) -> int:
        """Convert VADER compound score (-1.0 to 1.0) to 1-10 integer scale."""
        score = round(((compound + 1) / 2) * 9 + 1)
        return max(1, min(10, score))

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

        confidence = min(1.0, volume / 5) if volume > 0 else 0.0

        return {
            "fixture": fixture_name,
            "sentiment_score": score,
            "sentiment_score_1_10": self._compound_to_1_10(score),
            "confidence": confidence,
            "volume": volume,
            "headlines": headlines or []
        }
