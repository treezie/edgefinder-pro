
import asyncio
import logging
from scrapers.mock_scraper import MockScraper
from analysis.pipeline import AnalysisPipeline

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_nba_fetch():
    print("--- Debugging NBA Fetch ---")
    scraper = MockScraper("NBA")
    
    print("1. Fetching games from scraper...")
    try:
        games = await scraper.fetch_odds()
        print(f"2. Scraper returned {len(games)} betting options/fixtures")
        
        if games:
            print(f"   Sample fixture: {games[0]}")
            # Check dates
            print(f"   First game time: {games[0]['start_time']}")
            
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            future_games = [g for g in games if g['start_time'] > now]
            print(f"3. Future games count: {len(future_games)} (Now: {now})")
        else:
            print("   WARNING: No games returned. Check API keys or schedule.")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(debug_nba_fetch())
