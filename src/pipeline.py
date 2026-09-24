"""Global Crypto Sentiment Index -- one real snapshot per run, blending:
  - momentum: market-cap-weighted 24h price momentum across the top N
    coins (CoinGecko, every run -- the one call that must succeed)
  - community: real crowd-sourced sentiment votes CoinGecko itself
    collects per coin (cached, refreshed on a timer -- see config)
  - news: VADER sentiment on live crypto headlines (Google News RSS,
    cached, refreshed on the same timer)

Runs every 3 minutes on the VM's own crontab (~480 real snapshots/day).
Both community and news are cached/timer-based rather than fetched every
run: CoinGecko's free tier rate-limits hard on bursts (observed a 429
after just 3 calls in quick succession during local testing), so hitting
it for community sentiment every 3 minutes isn't viable -- only the
single bulk /coins/markets call happens every cycle.

Appends one compact row to data/sentiment_history.csv per run -- NOT a
full-file rewrite -- learned the hard way on East_Africa_News_Sentiment
today that committing a full growing file on every cron cycle silently
fills a VM's disk over a few months. A 3-minute cadence makes that
mistake catastrophic within weeks instead, so this pipeline is designed
around small, bounded, append-only writes from the start.
"""

import json
from datetime import datetime, timezone

import requests

import market
import news_sentiment
from config import (
    COMMUNITY_REFRESH_INTERVAL_MINUTES,
    DATA_JSON,
    HISTORY_CSV,
    NEWS_REFRESH_INTERVAL_MINUTES,
    RECENT_POINTS_FOR_CHART,
    STATE_JSON,
    WEIGHT_COMMUNITY,
    WEIGHT_MOMENTUM,
    WEIGHT_NEWS,
)


def _recent_history_for_chart(limit=RECENT_POINTS_FOR_CHART):
    """Tail of the CSV as a compact [{t, v}] list -- lets the dashboard
    draw a trend line without shipping or parsing the full growing CSV
    client-side.
    """
    if not HISTORY_CSV.exists():
        return []
    with open(HISTORY_CSV) as f:
        lines = f.read().splitlines()
    if len(lines) <= 1:
        return []
    header = lines[0].split(",")
    ts_idx = header.index("timestamp")
    idx_idx = header.index("sentiment_index")
    rows = lines[-limit:] if len(lines) - 1 > limit else lines[1:]
    points = []
    for line in rows:
        if line == lines[0]:
            continue
        parts = line.split(",")
        try:
            points.append({"t": parts[ts_idx], "v": float(parts[idx_idx])})
        except (ValueError, IndexError):
            continue
    return points


def _load_state():
    if STATE_JSON.exists():
        with open(STATE_JSON) as f:
            return json.load(f)
    return {}


def _save_state(state):
    STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_JSON, "w") as f:
        json.dump(state, f, indent=2)


def _maybe_cached(state, key, interval_minutes, fetch_fn):
    """Returns (value, refreshed). Reuses the cached value from state if
    it's younger than interval_minutes; otherwise calls fetch_fn() and
    falls back to the stale cached value (not None) if that call fails --
    a transient error shouldn't blank out a real recent signal.
    """
    fetched_at_key, value_key = f"{key}_fetched_at", f"{key}_value"
    last_at = state.get(fetched_at_key)
    cached_value = state.get(value_key)
    if last_at is not None:
        elapsed_min = (datetime.now(timezone.utc) - datetime.fromisoformat(last_at)).total_seconds() / 60
        if elapsed_min < interval_minutes:
            return cached_value, False

    try:
        fresh = fetch_fn()
    except requests.RequestException as e:
        print(f"[pipeline] {key} fetch failed, keeping cached value: {e}")
        return cached_value, False
    if fresh is None:
        return cached_value, False
    return fresh, True


def run():
    try:
        coins = market.fetch_top_coins()
    except requests.RequestException as e:
        print(f"[pipeline] market data fetch failed, skipping this cycle: {e}")
        return None
    momentum = market.momentum_score(coins)

    state = _load_state()
    community, community_refreshed = _maybe_cached(
        state, "community", COMMUNITY_REFRESH_INTERVAL_MINUTES, market.community_score
    )
    news, news_refreshed = _maybe_cached(
        state, "news", NEWS_REFRESH_INTERVAL_MINUTES, news_sentiment.news_score
    )

    components = {"momentum": momentum, "community": community, "news": news}
    weights = {"momentum": WEIGHT_MOMENTUM, "community": WEIGHT_COMMUNITY, "news": WEIGHT_NEWS}
    available = {k: v for k, v in components.items() if v is not None}
    weight_sum = sum(weights[k] for k in available) or 1.0
    index = sum(v * weights[k] for k, v in available.items()) / weight_sum

    btc = next((c for c in coins if c["id"] == "bitcoin"), None)
    eth = next((c for c in coins if c["id"] == "ethereum"), None)
    gainer = max(coins, key=lambda c: c.get("price_change_percentage_24h") or -999)
    loser = min(coins, key=lambda c: c.get("price_change_percentage_24h") or 999)

    now = datetime.now(timezone.utc)
    row = {
        "timestamp": now.isoformat(),
        "sentiment_index": round(index, 2),
        "momentum_component": round(momentum, 2) if momentum is not None else "",
        "community_component": round(community, 2) if community is not None else "",
        "news_component": round(news, 2) if news is not None else "",
        "btc_price": btc["current_price"] if btc else "",
        "btc_change_24h": round(btc["price_change_percentage_24h"], 2) if btc and btc.get("price_change_percentage_24h") is not None else "",
        "eth_price": eth["current_price"] if eth else "",
        "eth_change_24h": round(eth["price_change_percentage_24h"], 2) if eth and eth.get("price_change_percentage_24h") is not None else "",
        "top_gainer": gainer["symbol"].upper(),
        "top_gainer_pct": round(gainer.get("price_change_percentage_24h") or 0, 2),
        "top_loser": loser["symbol"].upper(),
        "top_loser_pct": round(loser.get("price_change_percentage_24h") or 0, 2),
    }

    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not HISTORY_CSV.exists()
    with open(HISTORY_CSV, "a") as f:
        if is_new:
            f.write(",".join(row.keys()) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")

    DATA_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_JSON, "w") as f:
        json.dump(
            {"latest": row, "generated_at": now.isoformat(), "recent": _recent_history_for_chart()},
            f, indent=2,
        )

    if community_refreshed:
        state["community_fetched_at"] = now.isoformat()
        state["community_value"] = community
    if news_refreshed:
        state["news_fetched_at"] = now.isoformat()
        state["news_value"] = news
    _save_state(state)

    btc_price_str = f"${row['btc_price']:,}" if isinstance(row["btc_price"], (int, float)) else "N/A"
    print(
        f"[pipeline] index={row['sentiment_index']} "
        f"(momentum={row['momentum_component']}, "
        f"community={row['community_component']}{'*' if community_refreshed else ''}, "
        f"news={row['news_component']}{'*' if news_refreshed else ''}) "
        f"BTC={btc_price_str} ({row['btc_change_24h']}%) "
        f"top gainer {row['top_gainer']} {row['top_gainer_pct']}%"
    )
    return row


if __name__ == "__main__":
    run()
