# Betting Suggestion App

A sophisticated betting suggestion application that identifies value opportunities using odds analysis, historical data, and sentiment analysis.

## Features
- **Mock Data Generation**: Simulates odds, historical stats, and sentiment for testing.
- **Value Analysis**: Calculates "True Probability" and identifies +EV bets.
- **Dashboard**: Web interface to view recommended bets with confidence scores.

## Setup & Installation

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Initialize Database**:
    ```bash
    python init_db.py
    ```

3.  **Run the Analysis Pipeline** (Populate Data):
    ```bash
    python analysis/pipeline.py
    ```

4.  **Start the Web Server**:
    ```bash
    cd C:\Users\luket\.gemini\antigravity\scratch\betting_app
    python -m uvicorn api.main:app --reload --port 8001
    ```

5.  **View the Dashboard**:
    Open your browser to `http://127.0.0.1:8000`.

## Architecture
- `scrapers/`: Modules for fetching data (currently mocked).
- `database/`: SQLAlchemy models and SQLite database.
- `analysis/`: Logic for calculating value and generating predictions.
- `api/`: FastAPI backend and HTML templates.

## Note on Data Sources
The current implementation uses `MockScraper` to generate data because live betting sites are often blocked in development environments. To use real data, implement the `fetch_odds` method in `scrapers/sportsbet_scraper.py` using Playwright selectors.
