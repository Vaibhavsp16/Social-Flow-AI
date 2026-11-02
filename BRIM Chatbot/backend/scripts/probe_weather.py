import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

print("geocode:", end=" ")
try:
    r = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": "Mumbai", "count": 1, "language": "en", "format": "json"},
        timeout=15,
    )
    print(r.status_code, r.text[:160])
    if r.status_code == 200 and r.json().get("results"):
        loc = r.json()["results"][0]
        params = {
            "latitude": loc["latitude"], "longitude": loc["longitude"],
            "current": "temperature_2m,weather_code", "timezone": "auto",
        }
        f = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=15)
        print("forecast:", f.status_code, f.text[:200])
except Exception as exc:  # noqa: BLE001
    print("geocode FAILED", type(exc).__name__, exc)

print("wttr:", end=" ")
try:
    w = httpx.get("https://wttr.in/Mumbai?format=j1", timeout=20)
    print(w.status_code, w.text[:120])
except Exception as exc:  # noqa: BLE001
    print("FAILED", type(exc).__name__, str(exc)[:100])
