"""
Greeting engine: context → decision → message.

Decision priority is holiday > notable weather > time of day, so a festival greeting is never
buried under small talk. All wording comes from the message catalogue; this module only decides
which key to use and whether an optional light question is appropriate.
"""

import os
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from app.core.messages import SUPPORTED_LANGUAGES, translate
from app.services.holiday_service import HolidayService
from app.services.language_service import LanguageService
from app.services.weather_service import WeatherService

DEFAULT_OFFSET_MINUTES = 330  # Asia/Kolkata


def _roll(seed: str, salt: str) -> float:
    """Deterministic 0-1 value so the same conversation always gets the same greeting."""
    return (zlib.crc32(f"{seed}:{salt}".encode("utf-8")) % 100) / 100.0


class GreetingService:

    @staticmethod
    def _time_of_day(local_hour: Optional[int], utc_offset_minutes: Optional[int]) -> int:
        if local_hour is not None and 0 <= int(local_hour) <= 23:
            return int(local_hour)
        offset = utc_offset_minutes if utc_offset_minutes is not None else DEFAULT_OFFSET_MINUTES
        shifted = datetime.now(timezone.utc) + timedelta(minutes=int(offset))
        return shifted.hour

    @staticmethod
    def _time_key(hour: int) -> str:
        if 5 <= hour < 12:
            return "greeting_morning"
        if 12 <= hour < 17:
            return "greeting_afternoon"
        if 17 <= hour < 22:
            return "greeting_evening"
        return "greeting_late_night"

    @staticmethod
    def _is_custom_welcome(welcome: Optional[str]) -> bool:
        """
        True only for copy the owner actually wrote.

        The platform default ("Hi! How can I help you today?") is identical to the generic
        intent question, so honouring it would greet the visitor and then ask the same thing.
        """
        candidate = (welcome or "").strip()
        if len(candidate) < 12:
            return False
        generic = [
            translate(code, "ask_intent_general").strip().lower().rstrip(" .!?")
            for code in SUPPORTED_LANGUAGES
        ]
        normalised = candidate.lower().rstrip(" .!?")
        # "Hi! How can I help you today?" is the platform default with a greeting prefix;
        # treating it as custom copy would open with the same sentence twice.
        return not any(phrase and phrase in normalised for phrase in generic)



    @classmethod
    def build(
        cls,
        bot_name: str,
        language: Optional[str] = None,
        city: Optional[str] = None,
        region: Optional[str] = None,
        local_hour: Optional[int] = None,
        utc_offset_minutes: Optional[int] = None,
        language_hint: Optional[str] = None,
        include_engagement: bool = True,
        seed: str = "new-conversation",
        industry: Optional[str] = None,
        welcome: Optional[str] = None,
    ) -> Dict[str, Any]:
        lang = (
            LanguageService.normalise(language)
            or LanguageService.normalise(language_hint)
            or "en"
        )

        hour = cls._time_of_day(local_hour, utc_offset_minutes)
        time_key = cls._time_key(hour)
        time_of_day = time_key.replace("greeting_", "")

        # The property-flavoured greetings and intent question only fit a Real Estate bot.
        # Every other industry gets the neutral variants, so an FMCG bot never introduces
        # itself as "the property assistant for Prycoons".
        is_property_bot = (industry or "").strip().lower() == "real estate"
        if not is_property_bot:
            time_key = f"{time_key}_general"
        intent_key = "ask_intent" if is_property_bot else "ask_intent_general"

        holiday = HolidayService.on(language=lang)
        weather = WeatherService.get(city) if city else {"available": False}

        engagement_enabled = os.getenv("ENGAGEMENT_ENABLED", "true").lower() in ("1", "true", "yes")
        weather_probability = float(os.getenv("WEATHER_MENTION_PROBABILITY", "0.35"))

        greet_weather = bool(
            weather.get("available")
            and (weather.get("notable") or _roll(seed, "weather") < weather_probability)
        )

        # Opening line: one short welcome. Time-of-day and holiday phrasing is kept in the
        # context payload but no longer opens the chat — the first message is not a status
        # report.
        if cls._is_custom_welcome(welcome):
            # A bot's saved welcome message is the owner's copy — use it verbatim rather than
            # overwriting it with the generic time-of-day line.
            text = welcome.strip()
            decision = "custom_welcome"
        else:
            text = translate(lang, "welcome_opening")
            decision = "welcome"

        # One short welcome, one open question. Stacking a time greeting, a weather note, an
        # intent menu and a personal question in the first message read as an interrogation.
        text += "\n\n" + translate(lang, "welcome_question")

        engagement = None

        return {
            "text": text,
            "language": lang,
            "decision": decision,
            "context": {
                "time_of_day": time_of_day,
                "local_hour": hour,
                "city": city,
                "region": region,
                "holiday": holiday.get("name") if holiday["is_holiday"] else None,
                "weather_available": bool(weather.get("available")),
                "weather_summary": weather.get("summary") if weather.get("available") else None,
                "engagement": engagement,
            },
        }
