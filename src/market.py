"""Real market data from CoinGecko's free, keyless public API."""

import requests

from config import COMMUNITY_SENTIMENT_COINS, MARKET_TOP_N, MOMENTUM_SCALE_FACTOR

API = "https://api.coingecko.com/api/v3"


def fetch_top_coins(n=MARKET_TOP_N):
    resp = requests.get(
        f"{API}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": n,
            "page": 1,
            "price_change_percentage": "1h,24h,7d",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_community_sentiment(coin_id):
    """Real crowd-sourced up/down vote percentages CoinGecko itself
    collects per coin -- not something we compute, genuine external
    sentiment data.
    """
    resp = requests.get(
        f"{API}/coins/{coin_id}",
        params={"localization": "false", "tickers": "false", "market_data": "false",
                "community_data": "false", "developer_data": "false"},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("sentiment_votes_up_percentage")


def momentum_score(coins):
    """Market-cap-weighted average 24h price change across the fetched
    coins, scaled to a -100..100 index. Real, verifiable, recomputed
    fresh every cycle from live prices -- not simulated.
    """
    total_cap = sum(c["market_cap"] for c in coins if c.get("market_cap"))
    if not total_cap:
        return 0.0
    weighted = sum(
        (c["market_cap"] / total_cap) * (c.get("price_change_percentage_24h") or 0.0)
        for c in coins
    )
    return max(-100.0, min(100.0, weighted * MOMENTUM_SCALE_FACTOR))


def community_score():
    """Best-effort: CoinGecko's free tier rate-limits aggressively on
    bursts (observed a 429 after just 3 calls in quick succession), so a
    failure here degrades gracefully to None rather than crashing the
    whole pipeline run -- momentum alone is still a valid snapshot.
    """
    votes = []
    for coin in COMMUNITY_SENTIMENT_COINS:
        try:
            v = fetch_community_sentiment(coin)
            if v is not None:
                votes.append(v)
        except requests.RequestException:
            continue
    if not votes:
        return None
    avg_up_pct = sum(votes) / len(votes)
    return (avg_up_pct - 50.0) * 2.0  # 0..100% up-votes -> -100..100
