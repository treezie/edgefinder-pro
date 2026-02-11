import asyncio
import random
from typing import Dict, Any, List
from datetime import datetime
import hashlib
from .injury_fetcher import InjuryFetcher


class ExpertAnalysisFetcher:
    """
    Fetches expert analysis and betting trends from multiple sources.
    In production, this would scrape from actual betting forums and expert sites.
    For demo, generates realistic analysis based on team/game data.
    """

    def __init__(self):
        self.sources = [
            "ESPN Expert Picks",
            "CBS Sports Analysis",
            "The Athletic",
            "Reddit r/sportsbook",
            "Covers.com Forum",
            "Action Network"
        ]
        self.injury_fetcher = InjuryFetcher()

    async def get_betting_trends(self, team_name: str, sport: str, opponent: str = None) -> Dict[str, Any]:
        """
        Get betting trends and expert consensus for a team.
        Returns consensus percentage, public betting %, and expert picks.
        """
        # Use team hash for consistent but varied results
        team_hash = int(hashlib.md5(f"{team_name}{opponent}".encode()).hexdigest(), 16)

        # Generate realistic betting trends
        public_betting_pct = 30 + (team_hash % 50)  # 30-80%
        expert_consensus = 40 + (team_hash % 40)    # 40-80%

        # Sharp money indicator (opposite of public sometimes)
        sharp_indicator = "with public" if (team_hash % 3) != 0 else "fading public"

        return {
            "public_betting_percentage": public_betting_pct,
            "expert_consensus": expert_consensus,
            "sharp_money": sharp_indicator,
            "trend_strength": "Strong" if expert_consensus > 65 else "Moderate" if expert_consensus > 50 else "Weak"
        }

    async def get_recent_form_analysis(self, team_name: str, record: str) -> Dict[str, Any]:
        """
        Analyze recent form based on record and generate insights.
        """
        try:
            if "-" in record:
                wins, losses = map(int, record.split("-")[:2])
                total_games = wins + losses

                # Calculate recent form metrics
                win_pct = wins / total_games if total_games > 0 else 0.5

                # Form indicators
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

                # Simulate last 5 games (L5)
                team_hash = int(hashlib.md5(team_name.encode()).hexdigest(), 16)
                l5_wins = min(5, int(win_pct * 5) + (team_hash % 2))
                l5_record = f"{l5_wins}-{5-l5_wins}"

                return {
                    "current_form": form,
                    "form_description": form_desc,
                    "last_5_games": l5_record,
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
        Generate head-to-head statistics and historical matchup data.
        """
        # Use consistent hash for h2h
        h2h_hash = int(hashlib.md5(f"{home_team}{away_team}{sport}".encode()).hexdigest(), 16)

        # Historical advantage
        home_h2h_wins = 2 + (h2h_hash % 4)  # 2-5 wins
        total_h2h = 5 + (h2h_hash % 3)      # 5-7 total games
        away_h2h_wins = total_h2h - home_h2h_wins

        # Home field advantage factor
        home_advantage = 52 + (h2h_hash % 10)  # 52-62%

        return {
            "h2h_record": f"{home_h2h_wins}-{away_h2h_wins}",
            "home_team_h2h_win_pct": round((home_h2h_wins / total_h2h) * 100, 1) if total_h2h > 0 else 50.0,
            "home_field_advantage": home_advantage,
            "h2h_summary": f"{home_team} leads series {home_h2h_wins}-{away_h2h_wins} in last {total_h2h} meetings"
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
        """
        # Fetch all analysis components
        betting_trends = await self.get_betting_trends(team_name, sport, opponent)
        form_analysis = await self.get_recent_form_analysis(team_name, record)
        h2h_analysis = await self.get_head_to_head_analysis(
            team_name if is_home else opponent,
            opponent if is_home else team_name,
            sport
        )
        injury_analysis = await self.get_injury_impact_analysis(team_name, sport)

        # Calculate overall confidence based on multiple factors
        confidence_score = 0
        reasoning_points = []

        # Factor 1: Recent Form (30% weight)
        if form_analysis["current_form"] in ["Hot", "Good"]:
            confidence_score += 30
            reasoning_points.append(f"✓ {form_analysis['form_description']}")
        elif form_analysis["current_form"] == "Average":
            confidence_score += 15
            reasoning_points.append(f"• {form_analysis['form_description']}")
        else:
            reasoning_points.append(f"✗ {form_analysis['form_description']}")

        # Factor 2: Betting Trends (20% weight)
        if betting_trends["expert_consensus"] > 60:
            confidence_score += 20
            reasoning_points.append(
                f"✓ Expert consensus {betting_trends['expert_consensus']}% on this pick"
            )
        elif betting_trends["expert_consensus"] > 50:
            confidence_score += 10
            reasoning_points.append(
                f"• Moderate expert support ({betting_trends['expert_consensus']}%)"
            )

        # Factor 3: Sharp Money (15% weight)
        if betting_trends["sharp_money"] == "with public":
            confidence_score += 15
            reasoning_points.append("✓ Sharp money aligns with public betting")
        else:
            confidence_score += 8
            reasoning_points.append("• Sharp money fading public (contrarian indicator)")

        # Factor 4: Home/Away and H2H (20% weight)
        if is_home and h2h_analysis["home_field_advantage"] > 55:
            confidence_score += 15
            reasoning_points.append(
                f"✓ Strong home advantage ({h2h_analysis['home_field_advantage']}%)"
            )
        if h2h_analysis["home_team_h2h_win_pct"] > 55:
            confidence_score += 5
            reasoning_points.append(f"✓ {h2h_analysis['h2h_summary']}")

        # Factor 5: Injury Impact (15% weight)
        if injury_analysis["impact"] == "Minimal":
            confidence_score += 15
            reasoning_points.append(f"✓ {injury_analysis['description']}")
        elif injury_analysis["impact"] == "Low":
            confidence_score += 10
        elif injury_analysis["impact"] == "Moderate":
            confidence_score += 5
            reasoning_points.append(f"⚠ {injury_analysis['description']}")
        else:
            reasoning_points.append(f"✗ {injury_analysis['description']}")

        return {
            "confidence_score": min(100, confidence_score),
            "reasoning_points": reasoning_points,
            "betting_trends": betting_trends,
            "form_analysis": form_analysis,
            "h2h_analysis": h2h_analysis,
            "injury_analysis": injury_analysis,
            "sources_consulted": random.sample(self.sources, 3)  # Show 3 random sources
        }
