"""Shared constants for the Global Crypto Sentiment Index."""

from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_DIR / "data"
DOCS_DIR = REPO_DIR / "docs"

HISTORY_CSV = DATA_DIR / "sentiment_history.csv"
DATA_JSON = DOCS_DIR / "data.json"

# Top N coins by market cap, fetched in a single CoinGecko call each
# cycle -- no API key needed, one request regardless of N.
MARKET_TOP_N = 20

# Coins whose CoinGecko community sentiment votes (real crowd data, not
# computed) get pulled. Kept small -- each is its own API call.
COMMUNITY_SENTIMENT_COINS = ["bitcoin", "ethereum"]

# Community sentiment is cached and refreshed on this timer, not every
# cycle -- CoinGecko's free tier rate-limited us after just 3 calls in
# quick succession during testing, so a 3-minute cadence can't afford
# 2 extra per-coin calls every single run.
COMMUNITY_REFRESH_INTERVAL_MINUTES = 15

# News headlines are cached and only refreshed once this many minutes
# have passed since the last fetch -- time-based rather than counting
# cycles, so it self-adjusts if the cron cadence ever changes. Avoids
# hammering Google News RSS every 3 minutes; 15 min matches the cadence
# East_Africa_News_Sentiment already uses successfully against the same
# source.
NEWS_REFRESH_INTERVAL_MINUTES = 15
NEWS_QUERY = "cryptocurrency bitcoin ethereum"
NEWS_HEADLINE_LIMIT = 20

STATE_JSON = DATA_DIR / "state.json"

# How many recent snapshots get embedded in docs/data.json for the
# dashboard's trend chart (~12 hours at a 3-minute cadence).
RECENT_POINTS_FOR_CHART = 240

# Composite index weights -- must sum to 1.0. Momentum carries the most
# weight since it's real-time and updates every cycle; community/news are
# slower-moving real signals blended in alongside it.
WEIGHT_MOMENTUM = 0.5
WEIGHT_COMMUNITY = 0.3
WEIGHT_NEWS = 0.2

# Scales average 24h price-change-% across the top N coins (market-cap
# weighted) up to a -100..100 index range. Typical daily moves are a few
# percent, so this factor keeps the index using its full range without
# saturating on ordinary days.
MOMENTUM_SCALE_FACTOR = 15
