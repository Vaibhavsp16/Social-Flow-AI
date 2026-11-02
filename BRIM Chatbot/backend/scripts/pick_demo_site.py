"""Probe candidate real-estate sites for crawlability before the demo run."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.document_processor import DocumentProcessor as DP

CANDIDATES = [
    "https://www.ashianahousing.com/",
    "https://www.lodhagroup.com/",
    "https://www.kalpataru.com/",
    "https://www.brigadegroup.com/",
]

for url in CANDIDATES:
    try:
        text, meta = DP.crawl_website(url, max_pages=2)
        print(f"OK    {url}  pages={meta['pages_crawled']} chars={meta['character_count']}")
        for page in meta["pages"]:
            print(f"        {page['url'][:95]} ({page['character_count']})")
    except Exception as exc:
        print(f"FAIL  {url}  {type(exc).__name__}: {str(exc)[:110]}")
