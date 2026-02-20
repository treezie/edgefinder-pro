import requests
from typing import Dict, List, Any
import asyncio

class InjuryFetcher:
    """
    Fetches real injury data from ESPN API
    """

    def __init__(self):
        self.nfl_base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"
        self.nba_base_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams"
        self.nrl_base_url = "https://site.api.espn.com/apis/site/v2/sports/rugby-league/nrl/teams"
        self.cache = {}  # Cache injury data to reduce API calls

    async def get_team_injuries(self, team_name: str, sport: str) -> Dict[str, Any]:
        """
        Fetch real injury report for a specific team from ESPN
        """
        cache_key = f"{sport}_{team_name}"

        # Return cached data if available
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: self._get_team_injuries_sync(team_name, sport))
        except Exception as e:
            print(f"⚠ Error fetching injury report for {team_name}: {e}")
            return self._get_empty_injury_report()

    def _get_team_injuries_sync(self, team_name: str, sport: str) -> Dict[str, Any]:
        cache_key = f"{sport}_{team_name}"
        try:
            # Get team roster and injuries
            if sport == "NFL":
                base_url = self.nfl_base_url
            elif sport == "NRL":
                base_url = self.nrl_base_url
            else:
                base_url = self.nba_base_url

            # First, get list of all teams to find the team ID
            response = requests.get(base_url, timeout=10)
            if response.status_code != 200:
                return self._get_empty_injury_report()

            teams_data = response.json()
            team_id = None

            # Find the matching team
            for team in teams_data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", []):
                team_info = team.get("team", {})
                if team_info.get("displayName") == team_name or team_info.get("name") == team_name:
                    team_id = team_info.get("id")
                    break

            if not team_id:
                print(f"⚠ Could not find team ID for {team_name}")
                return self._get_empty_injury_report()

            # Fetch team roster with injury data
            roster_url = f"{base_url}/{team_id}/roster"
            roster_response = requests.get(roster_url, timeout=10)

            if roster_response.status_code != 200:
                return self._get_empty_injury_report()

            roster_data = roster_response.json()

            # Extract injured players
            injured_players = []

            for athlete_entry in roster_data.get("athletes", []):
                for athlete in athlete_entry.get("items", []):
                    # Check if player has injury status
                    injury_status = athlete.get("injuries")

                    if injury_status and len(injury_status) > 0:
                        injury = injury_status[0]
                        status = injury.get("status", "UNKNOWN")

                        # Only include if actually injured (not "Active")
                        if status.upper() not in ["ACTIVE", "HEALTHY"]:
                            player_name = athlete.get("displayName", "Unknown Player")
                            position = athlete.get("position", {}).get("abbreviation", "N/A")
                            injury_type = injury.get("longComment") or injury.get("type") or "Unknown"

                            injured_players.append({
                                "name": player_name,
                                "position": position,
                                "status": status.upper(),
                                "injury": injury_type,
                                "impact": self._assess_impact(position, status)
                            })

            # Assess overall team impact
            result = {
                "status": self._get_overall_status(injured_players),
                "impact": self._get_overall_impact(injured_players),
                "description": self._generate_description(injured_players),
                "injured_players": injured_players
            }

            # Cache the result
            self.cache[cache_key] = result
            print(f"✓ Found {len(injured_players)} injured players for {team_name}")

            return result

        except Exception as e:
            print(f"⚠ Error fetching injuries for {team_name}: {e}")
            return self._get_empty_injury_report()

    def _get_empty_injury_report(self) -> Dict[str, Any]:
        """Return empty injury report when data is unavailable"""
        return {
            "status": "Full Strength",
            "impact": "Minimal",
            "description": "All key players available",
            "injured_players": []
        }

    def _assess_impact(self, position: str, status: str) -> str:
        """Assess the impact level of an injury based on position and status"""
        status = status.upper()

        # Key positions in each sport
        nfl_key_positions = ["QB", "RB", "WR", "TE", "LT", "DE", "LB"]
        nba_key_positions = ["PG", "SG", "SF", "PF", "C"]
        nrl_key_positions = ["FLB", "HLF", "FE", "HK", "LK"]

        is_key_position = (position in nfl_key_positions or
                           position in nba_key_positions or
                           position in nrl_key_positions)

        if status == "OUT":
            return "High - player ruled out" if is_key_position else "Moderate - backup unavailable"
        elif status == "DOUBTFUL":
            return "High - likely to miss game" if is_key_position else "Moderate - backup uncertain"
        elif status == "QUESTIONABLE":
            return "Moderate - game-time decision" if is_key_position else "Low - depth concern"
        else:
            return "Low - limited participation"

    def _get_overall_status(self, injured_players: List[Dict]) -> str:
        """Determine overall injury status"""
        if not injured_players:
            return "Full Strength"

        out_count = sum(1 for p in injured_players if p["status"] == "OUT")
        doubtful_count = sum(1 for p in injured_players if p["status"] == "DOUBTFUL")

        if out_count >= 2 or (out_count + doubtful_count) >= 3:
            return "Significant Injuries"
        elif out_count >= 1 or doubtful_count >= 2:
            return "Notable Absences"
        else:
            return "Minor Concerns"

    def _get_overall_impact(self, injured_players: List[Dict]) -> str:
        """Determine overall impact level"""
        if not injured_players:
            return "Minimal"

        high_impact = sum(1 for p in injured_players if "High" in p["impact"])
        moderate_impact = sum(1 for p in injured_players if "Moderate" in p["impact"])

        if high_impact >= 2:
            return "High"
        elif high_impact >= 1 or moderate_impact >= 2:
            return "Moderate"
        else:
            return "Low"

    def _generate_description(self, injured_players: List[Dict]) -> str:
        """Generate a summary description of injuries"""
        if not injured_players:
            return "All key players available"

        # Focus on the most impactful injuries
        out_players = [p for p in injured_players if p["status"] == "OUT"]
        doubtful_players = [p for p in injured_players if p["status"] == "DOUBTFUL"]

        if out_players:
            if len(out_players) == 1:
                return f"{out_players[0]['name']} ({out_players[0]['position']}) ruled OUT"
            else:
                return f"{len(out_players)} players ruled OUT including {out_players[0]['name']} ({out_players[0]['position']})"
        elif doubtful_players:
            return f"{doubtful_players[0]['name']} ({doubtful_players[0]['position']}) doubtful to play"
        else:
            return f"{len(injured_players)} player{'s' if len(injured_players) > 1 else ''} with injury designations"

    def clear_cache(self):
        """Clear the injury data cache"""
        self.cache.clear()
