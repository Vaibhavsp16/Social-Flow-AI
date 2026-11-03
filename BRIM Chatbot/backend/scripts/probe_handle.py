import re

import httpx
from bs4 import BeautifulSoup

UAS = {
    "browser": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "facebookexternalhit": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}
URL = "https://www.instagram.com/prycoons/"

for label, ua in UAS.items():
    try:
        with httpx.Client(timeout=30, follow_redirects=True) as c:
            r = c.get(URL, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
        print(f"{label}: HTTP {r.status_code} | {len(r.text)} bytes")
        soup = BeautifulSoup(r.text, "html.parser")
        for prop in ("og:title", "og:description", "description"):
            tag = soup.find("meta", attrs={"property": prop}) or soup.find(
                "meta", attrs={"name": prop}
            )
            if tag and tag.get("content"):
                print(f"   {prop}: {tag['content'][:160]}")
        for key in ("is_business_account", "business_category_name", "category_name", "is_verified"):
            found = re.search(rf'"{key}":([^,}}]+)', r.text)
            if found:
                print(f"   {key}: {found.group(1)[:60]}")
        if "Log in" in r.text or "login" in r.text.lower()[:4000]:
            print("   note: login wall present")
    except Exception as exc:  # noqa: BLE001
        print(f"{label}: ERROR {type(exc).__name__}: {exc}")
