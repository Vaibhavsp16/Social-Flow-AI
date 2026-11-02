"""
Rebuild the eight BRIM industry knowledge packs from the live industry pages.

Run from backend/:  python scripts/build_industry_packs.py

The packs are plain text snapshots committed under demo_documents/brim/, so seeding a bot for
an industry works offline during a demo. Re-run this when brim.co.in content changes.
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.industry_packs import BRIM_INDUSTRY_PACKS  # noqa: E402
from app.services.document_processor import DocumentProcessor  # noqa: E402

OUTPUT_DIR = BACKEND_ROOT / "demo_documents" / "brim"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0

    for pack in BRIM_INDUSTRY_PACKS:
        try:
            text, metadata = DocumentProcessor.crawl_website(pack["url"], max_pages=1)
        except Exception as exc:
            failures += 1
            print(f"[FAIL] {pack['key']}: {exc}")
            continue

        if len(text) < 400:
            failures += 1
            print(f"[WARN] {pack['key']}: only {len(text)} characters extracted - check the page")
            continue

        target = OUTPUT_DIR / pack["filename"]
        header = f"{pack['name']}\nSource: {pack['url']}\nIndustry: {pack['industry']}\n\n"
        target.write_text(header + text + "\n", encoding="utf-8")
        print(f"[ OK ] {pack['key']}: {len(text)} chars -> {target.name}")

    print(f"\nDone. {len(BRIM_INDUSTRY_PACKS) - failures}/{len(BRIM_INDUSTRY_PACKS)} packs built.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
