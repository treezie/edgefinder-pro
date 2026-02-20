import asyncio
from typing import Dict, Any

class HistoricalFetcher:
    def __init__(self, sport: str):
        self.sport = sport

    async def get_team_stats(self, team_name: str, record_data: str = None) -> Dict[str, Any]:
        """
        Fetches historical stats for a team.
        Uses real record data if provided. Returns neutral defaults when data is unavailable.
        """
        win_rate = 0.5
        form_desc = "Record unavailable"

        if record_data and "-" in record_data:
            try:
                parts = record_data.split("-")
                wins = int(parts[0])
                losses = int(parts[1])
                total = wins + losses

                if total == 0:
                    win_rate = 0.5
                    form_desc = "No record available"
                else:
                    win_rate = wins / total
                    form_desc = f"Record: {record_data}"
            except:
                win_rate = 0.5
                form_desc = "Record unavailable"

        return {
            "team": team_name,
            "win_rate": win_rate,
            "form_desc": form_desc
        }
