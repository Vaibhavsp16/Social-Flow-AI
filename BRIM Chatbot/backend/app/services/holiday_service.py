"""
Holiday/calendar abstraction.

Festivals live in a JSON file (demo_documents/holidays.json by default, override with
HOLIDAY_FILE) so the calendar is data, not code. A holiday outranks weather and time-of-day
when the greeting is chosen.
"""

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HolidayService:

    _cache: Dict[str, Any] = {"mtime": None, "holidays": {}}

    @classmethod
    def _path(cls) -> Path:
        configured = os.getenv("HOLIDAY_FILE")
        if configured:
            return Path(configured)
        from app.services.knowledge_service import KnowledgeService

        return KnowledgeService._industry_pack_dir().parent / "holidays.json"

    @classmethod
    def _load(cls) -> Dict[str, Dict[str, Any]]:
        path = cls._path()
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return {}
        if cls._cache["mtime"] == mtime:
            return cls._cache["holidays"]

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            holidays = {row["date"]: row for row in payload.get("holidays", [])}
            cls._cache = {"mtime": mtime, "holidays": holidays}
            return holidays
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Could not read holiday calendar at {path}: {exc}")
            return {}

    @classmethod
    def on(cls, day: Optional[date] = None, language: str = "en") -> Dict[str, Any]:
        """
        Returns {is_holiday, name, localised_name, date}. Never raises.
        """
        target = (day or date.today()).isoformat()
        holiday = cls._load().get(target)
        if not holiday:
            return {"is_holiday": False, "name": None, "localised_name": None, "date": target}

        names = holiday.get("names") or {}
        return {
            "is_holiday": True,
            "name": holiday.get("name"),
            "localised_name": names.get(language) or holiday.get("name"),
            "date": target,
        }
