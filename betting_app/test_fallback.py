#!/usr/bin/env python3
"""
Test script to verify API-first, web scraping fallback system.
"""
import asyncio
import os
from scrapers.odds_api_fetcher import OddsAPIFetcher

async def test_fallback():
    print("=" * 60)
    print("Testing API-First with Web Scraping Fallback")
    print("=" * 60)

    # Test 1: With exhausted API key (should fall back to web scraping)
    print("\n[Test 1] API with exhausted quota (should use web scraping)")
    api_key = os.getenv('ODDS_API_KEY')
    fetcher = OddsAPIFetcher(api_key=api_key, enable_web_scraping=True)

    # The API is currently returning 401, so it should automatically fall back
    odds = await fetcher.get_all_markets_for_game("NBA", "Cleveland Cavaliers", "Portland Trail Blazers")

    if odds:
        print(f"✓ SUCCESS: Got {len(odds)} odds entries")
        print(f"  First odd: {odds[0]['selection']} @ {odds[0]['price']} ({odds[0]['bookmaker']})")
    else:
        print(f"✗ FAILED: No odds returned")

    print("\n" + "=" * 60)

    # Test 2: No API key (should use web scraping only)
    print("\n[Test 2] No API key (should use web scraping)")
    fetcher_no_key = OddsAPIFetcher(api_key=None, enable_web_scraping=True)

    odds2 = await fetcher_no_key.get_all_markets_for_game("NFL", "Detroit Lions", "Dallas Cowboys")

    if odds2:
        print(f"✓ SUCCESS: Got {len(odds2)} odds entries")
        print(f"  First odd: {odds2[0]['selection']} @ {odds2[0]['price']} ({odds2[0]['bookmaker']})")
    else:
        print(f"✗ FAILED: No odds returned")

    print("\n" + "=" * 60)
    print("\nTest completed!")

if __name__ == "__main__":
    asyncio.run(test_fallback())
