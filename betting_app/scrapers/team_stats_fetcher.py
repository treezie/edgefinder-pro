import requests
from typing import Dict, Any
import asyncio

class TeamStatsFetcher:
    """
    Fetches REAL team statistics from ESPN API
    Only uses actual data - no simulations
    """

    def __init__(self):
        self.nfl_base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        self.nba_base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
        self.cache = {}

    async def get_team_stats(self, team_name: str, sport: str) -> Dict[str, Any]:
        """
        Fetch real team statistics from ESPN
        """
        cache_key = f"{sport}_{team_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            loop = asyncio.get_event_loop()
            if sport == "NFL":
                stats = await loop.run_in_executor(None, lambda: self._get_nfl_team_stats(team_name))
            elif sport == "NBA":
                stats = await loop.run_in_executor(None, lambda: self._get_nba_team_stats(team_name))
            else:
                stats = self._get_empty_stats()
            
            if stats.get("available", True):  # Only cache if we got valid stats or a valid empty response
                self.cache[cache_key] = stats
            
            return stats

        except Exception as e:
            print(f"⚠ Error fetching team stats for {team_name}: {e}")
            return self._get_empty_stats()

    def _get_nfl_team_stats(self, team_name: str) -> Dict[str, Any]:
        """Fetch real NFL team statistics"""
        try:
            # Get teams list to find team ID
            teams_url = f"{self.nfl_base_url}/teams"
            response = requests.get(teams_url, timeout=10)

            if response.status_code != 200:
                return self._get_empty_stats()

            teams_data = response.json()
            team_id = None

            # Find matching team
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                if team_info.get("displayName") == team_name or team_info.get("name") == team_name:
                    team_id = team_info.get("id")
                    break

            if not team_id:
                print(f"⚠ Could not find team ID for {team_name}")
                return self._get_empty_stats()

            # Get team statistics
            stats_url = f"{self.nfl_base_url}/teams/{team_id}/statistics"
            stats_response = requests.get(stats_url, timeout=10)

            if stats_response.status_code != 200:
                return self._get_empty_stats()

            stats_data = stats_response.json()

            # Parse statistics
            team_stats = {
                "points_per_game": 0,
                "points_against_per_game": 0,
                "total_yards_per_game": 0,
                "passing_yards_per_game": 0,
                "rushing_yards_per_game": 0,
                "offensive_rank": 0,
                "defensive_rank": 0,
                "turnover_differential": 0,
                "third_down_pct": 0,
                "red_zone_pct": 0
            }

            # Extract stats from ESPN response
            splits = stats_data.get("splits", {}).get("categories", [])

            for category in splits:
                cat_name = category.get("name", "")
                stats = category.get("stats", [])

                for stat in stats:
                    stat_name = stat.get("name", "").lower()
                    value = stat.get("value", 0)

                    if "points per game" in stat_name or "ppg" in stat_name:
                        team_stats["points_per_game"] = float(value)
                    elif "total yards" in stat_name:
                        team_stats["total_yards_per_game"] = float(value)
                    elif "passing yards" in stat_name:
                        team_stats["passing_yards_per_game"] = float(value)
                    elif "rushing yards" in stat_name:
                        team_stats["rushing_yards_per_game"] = float(value)

            print(f"✓ Fetched real NFL stats for {team_name}")
            return team_stats

        except Exception as e:
            print(f"⚠ NFL stats fetch failed for {team_name}: {e}")
            return self._get_empty_stats()

    def _get_nba_team_stats(self, team_name: str) -> Dict[str, Any]:
        """Fetch real NBA team statistics"""
        try:
            # Get teams list
            teams_url = f"{self.nba_base_url}/teams"
            response = requests.get(teams_url, timeout=10)

            if response.status_code != 200:
                return self._get_empty_stats()

            teams_data = response.json()
            team_id = None
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                if team_info.get("displayName") == team_name or team_info.get("name") == team_name:
                    team_id = team_info.get("id")
                    break

            if not team_id:
                return self._get_empty_stats()

            # Get team statistics
            stats_url = f"{self.nba_base_url}/teams/{team_id}/statistics"
            stats_response = requests.get(stats_url, timeout=10)

            if stats_response.status_code != 200:
                return self._get_empty_stats()

            stats_data = stats_response.json()

            team_stats = {
                "points_per_game": 0,
                "points_against_per_game": 0,
                "field_goal_pct": 0,
                "three_point_pct": 0,
                "assists_per_game": 0,
                "rebounds_per_game": 0,
                "offensive_rating": 0,
                "defensive_rating": 0,
                "pace": 0,
                "true_shooting_pct": 0
            }

            # Extract stats
            # Structure: results -> stats -> categories -> stats
            results = stats_data.get("results", {})
            stats_container = results.get("stats", {})
            categories = stats_container.get("categories", [])

            for category in categories:
                stats = category.get("stats", [])

                for stat in stats:
                    stat_name = stat.get("displayName", "").lower()
                    value = stat.get("value", 0)

                    if "points per game" in stat_name:
                        team_stats["points_per_game"] = float(value)
                    elif "field goal percentage" in stat_name:
                        team_stats["field_goal_pct"] = float(value)
                    elif "three point" in stat_name and "percentage" in stat_name:
                        team_stats["three_point_pct"] = float(value)
                    elif "assists per game" in stat_name:
                        team_stats["assists_per_game"] = float(value)
                    elif "rebounds per game" in stat_name:
                        team_stats["rebounds_per_game"] = float(value)

            print(f"✓ Fetched real NBA stats for {team_name}")
            return team_stats

        except Exception as e:
            print(f"⚠ NBA stats fetch failed for {team_name}: {e}")
            return self._get_empty_stats()

    def _get_empty_stats(self) -> Dict[str, Any]:
        """Return empty stats when data unavailable"""
        return {
            "available": False,
            "message": "Team statistics not available"
        }
