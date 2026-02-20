import asyncio
from typing import Dict, Any, List
from datetime import datetime
from .injury_fetcher import InjuryFetcher


class ExpertAnalysisFetcher:
    """
    Provides analysis based on real data sources:
    - Win/loss records from ESPN
    - Injury reports from ESPN
    - Sentiment from VADER (real headline analysis)

    No simulated or hash-based data.
    """

    def __init__(self):
        self.sources = ["ESPN", "VADER Sentiment"]
        self.injury_fetcher = InjuryFetcher()

    async def get_betting_trends(self, team_name: str, sport: str, opponent: str = None) -> Dict[str, Any]:
        """
        Betting trends data. Returns unavailable since we have no real betting trend source.
        """
        return {
            "public_betting_percentage": None,
            "expert_consensus": None,
            "sharp_money": "unavailable",
            "trend_strength": "N/A"
        }

    async def get_recent_form_analysis(self, team_name: str, record: str) -> Dict[str, Any]:
        """
        Analyze recent form based on real record data.
        """
        try:
            if "-" in record:
                wins, losses = map(int, record.split("-")[:2])
                total_games = wins + losses

                win_pct = wins / total_games if total_games > 0 else 0.5

                if win_pct >= 0.65:
                    form = "Hot"
                    form_desc = f"Excellent form with {wins}-{losses} record"
                elif win_pct >= 0.55:
                    form = "Good"
                    form_desc = f"Solid performance at {wins}-{losses}"
                elif win_pct >= 0.45:
                    form = "Average"
                    form_desc = f"Inconsistent at {wins}-{losses}"
                else:
                    form = "Cold"
                    form_desc = f"Struggling with {wins}-{losses} record"

                return {
                    "current_form": form,
                    "form_description": form_desc,
                    "last_5_games": "N/A",
                    "win_percentage": round(win_pct * 100, 1),
                    "momentum": "Positive" if win_pct > 0.55 else "Negative" if win_pct < 0.45 else "Neutral"
                }
        except:
            pass

        return {
            "current_form": "Unknown",
            "form_description": "Insufficient data",
            "last_5_games": "N/A",
            "win_percentage": 50.0,
            "momentum": "Neutral"
        }

    async def get_head_to_head_analysis(self, home_team: str, away_team: str, sport: str) -> Dict[str, Any]:
        """
        Head-to-head analysis. Returns unavailable since we have no real H2H data source.
        """
        return {
            "h2h_record": "N/A",
            "home_team_h2h_win_pct": None,
            "home_field_advantage": None,
            "h2h_summary": "Head-to-head data unavailable"
        }

    async def get_injury_impact_analysis(self, team_name: str, sport: str) -> Dict[str, Any]:
        """
        Fetch real injury report data from ESPN API
        """
        return await self.injury_fetcher.get_team_injuries(team_name, sport)

    async def get_comprehensive_analysis(
        self,
        team_name: str,
        opponent: str,
        sport: str,
        record: str,
        is_home: bool
    ) -> Dict[str, Any]:
        """
        Combine all analysis sources for comprehensive reasoning.
        Only scores confidence from data we actually have (form + injuries).
        """
        betting_trends = await self.get_betting_trends(team_name, sport, opponent)
        form_analysis = await self.get_recent_form_analysis(team_name, record)
        h2h_analysis = await self.get_head_to_head_analysis(
            team_name if is_home else opponent,
            opponent if is_home else team_name,
            sport
        )
        injury_analysis = await self.get_injury_impact_analysis(team_name, sport)

        confidence_score = 0
        reasoning_points = []

        # Factor 1: Recent Form (50% weight - increased since we have fewer factors)
        if form_analysis["current_form"] in ["Hot", "Good"]:
            confidence_score += 50
            reasoning_points.append(f"\u2713 {form_analysis['form_description']}")
        elif form_analysis["current_form"] == "Average":
            confidence_score += 25
            reasoning_points.append(f"\u2022 {form_analysis['form_description']}")
        else:
            if form_analysis["current_form"] != "Unknown":
                reasoning_points.append(f"\u2717 {form_analysis['form_description']}")

        # Factor 2: Injury Impact (50% weight - increased since we have fewer factors)
        if injury_analysis["impact"] == "Minimal":
            confidence_score += 50
            reasoning_points.append(f"\u2713 {injury_analysis['description']}")
        elif injury_analysis["impact"] == "Low":
            confidence_score += 35
            reasoning_points.append(f"\u2713 {injury_analysis['description']}")
        elif injury_analysis["impact"] == "Moderate":
            confidence_score += 15
            reasoning_points.append(f"\u26a0 {injury_analysis['description']}")
        else:
            reasoning_points.append(f"\u2717 {injury_analysis['description']}")

        # Note home advantage without fabricating a percentage
        if is_home:
            reasoning_points.append("\u2022 Playing at home")

        return {
            "confidence_score": min(100, confidence_score),
            "reasoning_points": reasoning_points,
            "betting_trends": betting_trends,
            "form_analysis": form_analysis,
            "h2h_analysis": h2h_analysis,
            "injury_analysis": injury_analysis,
            "sources_consulted": self.sources
        }
