import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.document_processor import DocumentProcessor as DP

for url, pages in [("https://brim.co.in/industry/", 8), ("https://brim.co.in/", 3)]:
    print(f"\n== {url} max_pages={pages}")
    try:
        text, meta = DP.crawl_website(url, max_pages=pages)
        print(f"pages={meta['pages_crawled']} chars={meta['character_count']}")
        for page in meta["pages"]:
            print(f"  - {page['url']} ({page['character_count']})")
    except Exception as exc:
        import traceback

        print("FAILED:", type(exc).__name__, exc)
        traceback.print_exc()
