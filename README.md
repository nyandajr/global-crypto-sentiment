# Global Crypto Sentiment Index

A live, composite crypto market sentiment index — real price momentum,
real crowd-sourced sentiment votes, and real NLP on live news headlines,
blended into one number and refreshed every 3 minutes.

**[Live dashboard](https://nyandajr.github.io/global-crypto-sentiment/)**

## What the index actually measures

No single number can fully capture "market sentiment," so this blends
three genuinely different, independently verifiable signals rather than
inventing one from nothing:

- **Momentum (50%)** — market-cap-weighted 24h price change across the
  top 20 coins by market cap (CoinGecko), scaled to a -100..100 range.
  Refreshed every run.
- **Community (30%)** — CoinGecko's own crowd-sourced up/down sentiment
  votes for BTC and ETH — real user input, not computed from price.
  Refreshed every 15 minutes (see rate-limit note below).
- **News (20%)** — VADER sentiment analysis on live crypto headlines from
  Google News RSS. Refreshed every 15 minutes.

Momentum updates every 3-minute cycle since that's genuinely real-time
data (prices move constantly); community and news are cached and
refreshed on a slower timer, both because they don't change that fast in
practice and because CoinGecko's free, keyless API rate-limits hard on
bursts (observed a 429 after just 3 calls in quick succession during
testing) — the pipeline degrades gracefully to the last known value on a
failed refresh rather than crashing or zeroing out a real signal.

## Why every 3 minutes

Crypto markets don't close, don't have quiet regional hours the way an
East-Africa-scoped tracker does, and prices genuinely change on that
timescale — a 3-minute cadence produces real, distinguishable snapshots
around the clock, not padding.

## Data hygiene, learned the hard way

Built the same day `East_Africa_News_Sentiment`'s `.git` history hit 30GB
from committing a full growing CSV on every cron run for months without
ever being garbage-collected — filled the VM's disk to 100% and took
every tracker on the box down with it. At a 3-minute cadence that same
mistake would be catastrophic within weeks instead of months, so this
pipeline was designed around it from day one:

- Every commit **appends one compact row** (~150 bytes) to
  `data/sentiment_history.csv` — never rewrites the whole file.
- The VM's weekly `git gc` (added portfolio-wide after that incident)
  keeps `.git` itself compressed regardless.

## Data

- `docs/data.json` — latest snapshot, fetched by the dashboard.
- `data/sentiment_history.csv` — append-only history, one row per cycle.
- `data/state.json` — internal cache for the community/news refresh timers.
