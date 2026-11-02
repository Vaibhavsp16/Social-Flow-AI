"""
Weather abstraction.

Providers return a small snapshot or None; nothing here raises into the chat path. The default
provider is Open-Meteo, which needs no API key. Coordinates are used in memory for the request
only — they are never written to the database or the conversation state.
"""

import logging
import os
import time
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes → (description, notable)
WMO_CODES: Dict[int, tuple[str, bool]] = {
    0: ("clear skies", False),
    1: ("mostly clear", False),
    2: ("partly cloudy", False),
    3: ("overcast", False),
    45: ("foggy", True),
    48: ("freezing fog", True),
    51: ("light drizzle", True),
    53: ("drizzle", True),
    55: ("heavy drizzle", True),
    61: ("light rain", True),
    63: ("rain", True),
    65: ("heavy rain", True),
    71: ("light snow", True),
    73: ("snow", True),
    75: ("heavy snow", True),
    80: ("rain showers", True),
    81: ("rain showers", True),
    82: ("heavy showers", True),
    95: ("a thunderstorm", True),
    96: ("a thunderstorm with hail", True),
    99: ("a thunderstorm with hail", True),
}


class WeatherProvider:
    """Interface: return {city, temp_c, condition, notable} or None."""

    def fetch(self, city: str) -> Optional[Dict[str, object]]:
        raise NotImplementedError


class NullWeatherProvider(WeatherProvider):
    """Used when weather is disabled or no provider is configured."""

    def fetch(self, city: str) -> Optional[Dict[str, object]]:
        return None


class OpenMeteoProvider(WeatherProvider):
    """Free, keyless provider. Any failure degrades to 'unavailable'."""

    def fetch(self, city: str) -> Optional[Dict[str, object]]:
        if not city:
            return None
        try:
            with httpx.Client(timeout=6.0) as client:
                geo = client.get(
                    OPEN_METEO_GEOCODE, params={"name": city, "count": 1, "language": "en"}
                )
                if geo.status_code != 200:
                    return None
                results = (geo.json() or {}).get("results") or []
                if not results:
                    return None
                place = results[0]
                latitude, longitude = place["latitude"], place["longitude"]

                forecast = client.get(
                    OPEN_METEO_FORECAST,
                    params={"latitude": latitude, "longitude": longitude, "current_weather": "true"},
                )
                if forecast.status_code != 200:
                    return None
                current = (forecast.json() or {}).get("current_weather") or {}
                code = int(current.get("weathercode", -1))
                temp = current.get("temperature")
                condition, notable = WMO_CODES.get(code, ("unsettled weather", False))
                if temp is not None:
                    if temp >= 38:
                        condition, notable = "very hot", True
                    elif temp <= 10:
                        condition, notable = "quite cold", True
                return {
                    "city": place.get("name") or city,
                    "temp_c": temp,
                    "condition": condition,
                    "notable": notable,
                }
        except Exception as exc:  # noqa: BLE001
            logger.info(f"Weather lookup failed for {city!r}: {exc}")
            return None


class WttrInProvider(WeatherProvider):
    """
    Second keyless provider used when Open-Meteo is unreachable.

    Open-Meteo occasionally resets connections from some networks; wttr.in answers from a
    different host, so a single dead provider no longer removes weather entirely.
    """

    def fetch(self, city: str) -> Optional[Dict[str, object]]:
        if not city:
            return None
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(
                    f"https://wttr.in/{city}",
                    params={"format": "j1"},
                    headers={"User-Agent": "curl/8.0"},
                )
                if response.status_code != 200:
                    return None
                current = ((response.json() or {}).get("current_condition") or [{}])[0]
                temp = float(current.get("temp_C")) if current.get("temp_C") else None
                description = ""
                if current.get("weatherDesc"):
                    description = (current["weatherDesc"][0] or {}).get("value", "")
                condition = (description or "unsettled weather").lower()
                notable = any(
                    word in condition
                    for word in ("rain", "drizzle", "thunder", "storm", "snow", "fog", "mist")
                )
                if temp is not None:
                    if temp >= 38:
                        condition, notable = "very hot", True
                    elif temp <= 10:
                        condition, notable = "quite cold", True
                return {
                    "city": city,
                    "temp_c": temp,
                    "condition": condition,
                    "notable": notable,
                }
        except Exception as exc:  # noqa: BLE001
            logger.info(f"Fallback weather lookup failed for {city!r}: {exc}")
            return None


class ChainedProvider(WeatherProvider):
    """Tries providers in order and returns the first usable snapshot."""

    def __init__(self, providers):
        self.providers = providers

    def fetch(self, city: str) -> Optional[Dict[str, object]]:
        for provider in self.providers:
            snapshot = provider.fetch(city)
            if snapshot:
                return snapshot
        return None


class WeatherService:
    """Caches lookups briefly so a conversation does not hammer the provider."""

    TTL_SECONDS = 900
    # Keep the last successful snapshot per city: public weather endpoints throttle, so a live
    # demo should not lose weather entirely because one request was refused.
    LAST_GOOD_SECONDS = 12 * 3600
    _cache: Dict[str, tuple[float, Optional[Dict[str, object]]]] = {}
    _last_good: Dict[str, tuple[float, Dict[str, object]]] = {}

    @classmethod
    def _provider(cls) -> WeatherProvider:
        if os.getenv("WEATHER_ENABLED", "true").lower() not in ("1", "true", "yes"):
            return NullWeatherProvider()
        name = (os.getenv("WEATHER_PROVIDER") or "open-meteo").lower()
        if name == "none":
            return NullWeatherProvider()
        if name == "wttr":
            return WttrInProvider()
        return ChainedProvider((OpenMeteoProvider(), WttrInProvider()))

    @classmethod
    def get(cls, city: Optional[str]) -> Dict[str, object]:
        """
        Returns {available, city, temp_c, condition, notable, summary}. Never raises.
        """
        unavailable = {
            "available": False, "city": city, "temp_c": None,
            "condition": None, "notable": False, "summary": None,
        }
        if not city:
            return unavailable

        key = city.strip().lower()
        now = time.time()
        cached = cls._cache.get(key)
        if cached and now - cached[0] < cls.TTL_SECONDS:
            snapshot = cached[1]
        else:
            snapshot = cls._provider().fetch(city)
            if snapshot:
                cls._last_good[key] = (now, snapshot)
            else:
                recent = cls._last_good.get(key)
                if recent and now - recent[0] < cls.LAST_GOOD_SECONDS:
                    snapshot = recent[1]
            # Failures are cached briefly so a transient outage is retried within a minute
            # instead of hiding weather for the full TTL.
            cls._cache[key] = (now, snapshot)
            if snapshot is None:
                cls._cache[key] = (now - cls.TTL_SECONDS + 60, None)

        if not snapshot:
            return unavailable

        temp = snapshot.get("temp_c")
        condition = snapshot.get("condition")
        summary = f"{condition}, {round(temp)}°C" if temp is not None else condition
        return {
            "available": True,
            "city": snapshot.get("city") or city,
            "temp_c": temp,
            "condition": condition,
            "notable": bool(snapshot.get("notable")),
            "summary": summary,
        }
