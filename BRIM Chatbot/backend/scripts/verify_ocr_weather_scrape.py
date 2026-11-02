"""
Verify image OCR, live weather and a real-estate website crawl end to end.

Run from backend/:  python scripts/verify_ocr_weather_scrape.py
"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from PIL import Image, ImageDraw

from app.services.document_processor import DocumentProcessor
from app.services.weather_service import WeatherService

API = "http://127.0.0.1:8000/api"
TMP = Path("_verify_tmp")
TMP.mkdir(exist_ok=True)

CANDIDATES = [
    "https://www.brigadegroup.com/",
    "https://www.sobha.com/",
    "https://www.puravankara.com/",
    "https://www.kalpataru.com/",
]


def section(title):
    print(f"\n=== {title} ===")


def make_png() -> Path:
    image = Image.new("RGB", (1100, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.text((24, 40), "Skyline Crest - Palm Grove Road", fill="black")
    draw.text((24, 95), "3 BHK from INR 1.42 crore. Possession March 2027.", fill="black")
    draw.text((24, 145), "Amenities: rooftop pool, gym, 2 covered parking spaces.", fill="black")
    path = TMP / "brochure.png"
    image.save(path)
    return path


section("1. LIVE WEATHER")
for city in ("Ahmedabad", "Mumbai"):
    snapshot = WeatherService.get(city)
    print(f"{city}: available={snapshot.get('available')} temp={snapshot.get('temp_c')} "
          f"condition={snapshot.get('condition')} notable={snapshot.get('notable')}")

section("2. IMAGE OCR (vision provider)")
png = make_png()
try:
    text, meta = DocumentProcessor.extract_from_image(str(png))
    print("chars:", len(text))
    print("ocr_status:", meta.get("ocr_status"))
    print("text:", text[:200].replace("\n", " | "))
except Exception as exc:  # noqa: BLE001
    print("OCR FAILED:", exc)

section("3. REAL-ESTATE SITE PROBE")
best = None
for url in CANDIDATES:
    try:
        page_text, page_meta = DocumentProcessor.crawl_website(url, max_pages=1)
        print(f"{url}: pages={page_meta['pages_crawled']} chars={page_meta['character_count']}")
        if best is None and page_meta["character_count"] > 800:
            best = (url, page_text, page_meta)
    except Exception as exc:  # noqa: BLE001
        print(f"{url}: FAILED {type(exc).__name__}: {str(exc)[:120]}")

if not best:
    print("No candidate produced usable text.")
    sys.exit(0)

url, _, _ = best
print("chosen:", url)

section("4. FULL PIPELINE VIA API")
client = httpx.Client(timeout=300.0)
email = f"verify_{uuid.uuid4().hex[:6]}@brimtest.com"
token = client.post(
    f"{API}/auth/signup", json={"name": "Verify", "email": email, "password": "Verify@12345"}
).json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
project = client.post(
    f"{API}/projects", json={"name": "Verify", "industry": "Real Estate"}, headers=headers
).json()
bot = client.post(
    f"{API}/bots",
    json={"project_id": project["id"], "name": "Verify Real Estate", "status": "Live"},
    headers=headers,
).json()

with open(png, "rb") as handle:
    upload = client.post(
        f"{API}/bots/{bot['id']}/knowledge/upload",
        files={"file": ("brochure.png", handle, "image/png")},
        headers=headers,
    )
print("image upload:", upload.status_code, upload.json().get("processing_status"),
      "chunks=", upload.json().get("chunks_count"))

site = client.post(
    f"{API}/bots/{bot['id']}/knowledge/website",
    json={"url": url, "max_pages": 3},
    headers=headers,
)
body = site.json()
print("website:", site.status_code, body.get("processing_status"),
      "chunks=", body.get("chunks_count"))
if body.get("metadata_json"):
    meta = body["metadata_json"]
    print("pages_crawled:", meta.get("pages_crawled") if isinstance(meta, dict) else meta)

for question in (
    "What is the possession date for the 3 BHK at Skyline Crest?",
    "What does the website say about this developer's projects?",
):
    answer = client.post(
        f"{API}/bots/{bot['id']}/chat", json={"message": question}, headers=headers
    ).json()
    print(f"\nQ: {question}")
    print("A:", answer["reply"][:260].replace("\n", " | "))
    print("sources:", len(answer["sources"]), "confidence:", answer.get("confidence"))

print("\nbot_id:", bot["id"], "user:", email)
