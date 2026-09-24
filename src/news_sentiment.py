"""Real NLP sentiment on live crypto news headlines -- Google News RSS
(keyless, same proven source East_Africa_News_Sentiment already uses
successfully) scored with VADER.
"""

import urllib.parse
import xml.etree.ElementTree as ET

import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import NEWS_HEADLINE_LIMIT, NEWS_QUERY

_analyzer = SentimentIntensityAnalyzer()


def fetch_headlines(query=NEWS_QUERY, limit=NEWS_HEADLINE_LIMIT):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    titles = [item.findtext("title") for item in root.findall(".//item")]
    return [t for t in titles if t][:limit]


def news_score():
    """Average VADER compound sentiment across the latest headlines,
    scaled from -1..1 to -100..100 to match the other index components.
    Returns None (caller keeps the previous value) if the feed is
    unreachable or empty, rather than zeroing out a real signal on a
    transient failure.
    """
    try:
        headlines = fetch_headlines()
    except requests.RequestException:
        return None
    if not headlines:
        return None
    scores = [_analyzer.polarity_scores(h)["compound"] for h in headlines]
    return (sum(scores) / len(scores)) * 100
