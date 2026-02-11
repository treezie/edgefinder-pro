# Real Odds System with API Fallback

## Overview
Your betting app now uses a **two-tier system** to ensure you always get REAL odds, never fake/demo data:

## Tier 1: The Odds API (Primary Source)
- **Source**: The Odds API (https://the-odds-api.com/)
- **Coverage**: 20+ bookmakers including SportsBet, TAB, Bet365, DraftKings, FanDuel, etc.
- **Markets**: Moneyline (h2h), Spreads, Totals (Over/Under)
- **Quota**: 500 requests/month (free tier)
- **Priority**: ALWAYS tries this first

## Tier 2: ESPN Web Scraping (Fallback Source)
- **Source**: ESPN's public betting API
- **Coverage**: DraftKings, FanDuel, Caesars, BetMGM (via ESPN partnerships)
- **Markets**: Moneyline (h2h), Spreads, Totals (Over/Under)
- **Quota**: Unlimited (public API)
- **Activation**: Automatically used when:
  - The Odds API quota is exhausted (401 error)
  - The Odds API is rate limited (429 error)
  - The Odds API has server errors (500+ errors)
  - No API key is provided

## How It Works

### 1. Normal Operation (API Available)
```
User requests data
    ↓
Try The Odds API
    ↓
✓ Success: Return real odds from 20+ bookmakers
```

### 2. Fallback Operation (API Exhausted)
```
User requests data
    ↓
Try The Odds API
    ↓
❌ 401 Error: Quota exhausted
    ↓
✓ Fall back to ESPN web scraping
    ↓
✓ Success: Return real odds from ESPN sources
```

### 3. No Data Available
```
User requests data
    ↓
Try The Odds API → No data
    ↓
Try ESPN scraping → No data
    ↓
⚠ Game not displayed (no fake data)
```

## Key Features

### ✅ REAL Data Only
- **NO demo mode**
- **NO simulated odds**
- **NO fake data**
- If no real odds are available, the game is simply not displayed

### ✅ Automatic Fallback
- Seamlessly switches to web scraping when API fails
- No manual intervention required
- User never sees errors or broken functionality

### ✅ Data Validation
- All odds must be between 1.01 and 50.0
- Value scores > 2.0 are rejected (indicates bad data)
- Betting exchange "lay" markets are filtered out
- Only requested markets (h2h, spreads, totals) are accepted

### ✅ Smart Caching
- After first API failure, quota is marked as exhausted
- Subsequent requests skip API and go straight to web scraping
- Saves unnecessary API calls
- Faster response times

## What Data You Get

### From The Odds API (When Available)
```
✓ 20+ bookmakers per game
✓ 100+ odds entries per game
✓ All three markets (h2h, spreads, totals)
✓ Australian bookmakers: SportsBet, TAB, Neds, Ladbrokes, etc.
✓ US bookmakers: DraftKings, FanDuel, BetMGM, Caesars, etc.
```

### From ESPN Web Scraping (When API Exhausted)
```
✓ 1 bookmaker per game (typically DraftKings)
✓ 6 odds entries per game
✓ All three markets (h2h, spreads, totals)
✓ Converted from American to decimal odds
✓ Updated in real-time from ESPN
```

## Testing

Run the test script to verify the system:
```bash
cd betting_app
python3 test_fallback.py
```

Expected output:
```
[Test 1] API with exhausted quota (should use web scraping)
❌ API Authentication failed - check your API key
   ↳ Falling back to web scraping...
🌐 Web scraping odds for Cleveland Cavaliers vs Portland Trail Blazers...
✓ Web scraped 6 odds for Cleveland Cavaliers vs Portland Trail Blazers
✓ SUCCESS: Got 6 odds entries
```

## Monitoring

Check the server logs to see which source is being used:
```
✓ Fetched 100 odds across all markets for Detroit Lions vs Dallas Cowboys
  → Using The Odds API

❌ API Authentication failed - check your API key
   ↳ Falling back to web scraping...
✓ Web scraped 6 odds for Detroit Lions vs Dallas Cowboys
  → Using ESPN web scraping
```

## Configuration

### Enable/Disable Web Scraping
In `scrapers/odds_api_fetcher.py`:
```python
# Enable web scraping fallback (default: True)
fetcher = OddsAPIFetcher(api_key=your_key, enable_web_scraping=True)

# Disable web scraping (API only)
fetcher = OddsAPIFetcher(api_key=your_key, enable_web_scraping=False)
```

### API Key
Set in `.env` file:
```
ODDS_API_KEY=your_api_key_here
```

## Benefits

1. **Reliability**: Never run out of data
2. **Cost Effective**: Free tier API + unlimited web scraping
3. **Data Quality**: Only real odds, no fake data
4. **User Experience**: Seamless, no errors shown to user
5. **Future Proof**: Easy to add more web scraping sources

## Limitations

### ESPN Web Scraping Limitations
- Only 1 bookmaker per game (vs 20+ from API)
- Fewer odds entries per game (6 vs 100+)
- Only games with ESPN betting data (most major games)
- Some games may not have odds available

### When Games Are Skipped
A game will not be displayed if:
- The Odds API has no data for it
- ESPN has no betting data for it
- The game has already started or finished
- Odds are outside the valid range (1.01-50.0)

## Future Enhancements

Potential additional web scraping sources:
- Oddschecker (UK/AU odds comparison)
- BetExplorer (International odds)
- Oddsportal (Global odds archive)
- Direct bookmaker sites (with proper rate limiting)

## Summary

Your app now has a **robust, reliable system** that:
- ✅ Always tries the best source first (The Odds API)
- ✅ Automatically falls back to web scraping when needed
- ✅ Never shows fake/demo data
- ✅ Provides real odds from real bookmakers
- ✅ Works even when API quota is exhausted

**Result**: You get real betting odds, always.
