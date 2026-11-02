"""
Language resolution.

Order of precedence: explicit selection → script/word detection from the message → browser
preference (Accept-Language) → English. Detection never changes conversation state; the flow
keeps the same slots and stage and only switches the wording.
"""

import re
from typing import Dict, Optional

from app.core.messages import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
GUJARATI = re.compile(r"[\u0A80-\u0AFF]")
TAMIL = re.compile(r"[\u0B80-\u0BFF]")
TELUGU = re.compile(r"[\u0C00-\u0C7F]")
BENGALI = re.compile(r"[\u0980-\u09FF]")
KANNADA = re.compile(r"[\u0C80-\u0CFF]")
LATIN = re.compile(r"[A-Za-z]")

# Marathi uses Devanagari too; these words separate it from Hindi.
MARATHI_MARKERS = {"आहे", "आहेत", "नाही", "मला", "तुम्ही", "पाहिजे", "कृपया", "भाड्याने", "काय"}
HINDI_MARKERS = {"है", "हैं", "नहीं", "मुझे", "आप", "चाहिए", "कृपया", "किराए", "घर"}

# Romanised Hindi/Gujarati is common in chat ("mujhe 3 bhk chahiye").
HINGLISH_MARKERS = {
    "mujhe", "chahiye", "chaiye", "kya", "hai", "nahi", "ghar", "kiraya", "kirae",
    "dikhao", "batao", "kitna", "paas", "mein", "achha",
}
GUJLISH_MARKERS = {"mane", "joiye", "che", "nathi", "bhav", "ghar", "batavo", "kidhu"}


class LanguageService:

    @staticmethod
    def supported() -> Dict[str, str]:
        return dict(SUPPORTED_LANGUAGES)

    @staticmethod
    def normalise(code: Optional[str]) -> Optional[str]:
        """'hi-IN' → 'hi' when we have that language, else None."""
        if not code:
            return None
        base = code.split("-")[0].strip().lower()
        return base if base in SUPPORTED_LANGUAGES else None

    @classmethod
    def detect(cls, text: str) -> str:
        """Best-effort language of a message. Always returns a supported code."""
        text = (text or "").strip()
        if not text:
            return DEFAULT_LANGUAGE

        if GUJARATI.search(text):
            return "gu"
        if DEVANAGARI.search(text):
            words = set(re.findall(r"[\u0900-\u097F]+", text))
            marathi_hits = len(words & MARATHI_MARKERS)
            hindi_hits = len(words & HINDI_MARKERS)
            return "mr" if marathi_hits > hindi_hits else "hi"
        if TAMIL.search(text) or TELUGU.search(text) or BENGALI.search(text) or KANNADA.search(text):
            # Recognised but not translated yet: answer in English rather than garbling.
            return DEFAULT_LANGUAGE

        if LATIN.search(text):
            tokens = set(re.findall(r"[a-z]+", text.lower()))
            if len(tokens & GUJLISH_MARKERS) >= 2:
                return "gu"
            if len(tokens & HINGLISH_MARKERS) >= 2:
                return "hi"
            return DEFAULT_LANGUAGE

        return DEFAULT_LANGUAGE

    @classmethod
    def resolve(
        cls,
        explicit: Optional[str],
        text: str = "",
        browser_preference: Optional[str] = None,
        current: Optional[str] = None,
    ) -> str:
        """
        Pick the language for this turn.

        An explicit choice wins. Otherwise a clearly different language in the message switches
        the conversation; an ambiguous message keeps the current language so the bot does not
        flip back and forth.
        """
        chosen = cls.normalise(explicit)
        if chosen:
            return chosen

        detected = cls.detect(text)
        if text and detected != DEFAULT_LANGUAGE:
            return detected
        if current:
            # A genuinely English message in a Hindi/Gujarati thread switches back to English,
            # but a stray brand word ("3 BHK") must not flip the conversation.
            if current != DEFAULT_LANGUAGE and len(re.findall(r"[A-Za-z]{2,}", text)) >= 3:
                return DEFAULT_LANGUAGE
            return current
        browser = cls.normalise(browser_preference)
        if browser:
            return browser
        return DEFAULT_LANGUAGE
