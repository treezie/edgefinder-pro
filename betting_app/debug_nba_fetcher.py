
import asyncio
from scrapers.player_stats_fetcher import PlayerStatsFetcher

async def debug_nba():
    fetcher = PlayerStatsFetcher()
    
    teams_to_test = [
        "Oklahoma City Thunder",
        "San Antonio Spurs",
        "Los Angeles Lakers",  # common one
        "Boston Celtics"
    ]
    
    print("Testing NBA Team Fetching...")
    
    for team in teams_to_test:
        print(f"\n--- Fetching {team} ---")
        players = await fetcher.get_top_players(team, "NBA")
        if players:
            print(f"✅ Found {len(players)} players")
            print(f"Sample: {players[0]}")
        else:
            print(f"❌ No players found for {team}")

if __name__ == "__main__":
    asyncio.run(debug_nba())
