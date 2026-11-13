"""Custom domains, kept in the company's own name.

The company owns the domain and points it at us; we never register or transfer anything. Two checks
prove control without asking for registrar credentials:

* a DNS **TXT** record at ``_brim-verify.<domain>`` holding a per-bot token, or
* a **CNAME** from ``<domain>`` to the host we serve the app from.

Either one passing is enough: the TXT route works when the domain is still pointed elsewhere (the
normal case while setting up), and the CNAME route confirms the domain is already serving traffic.
Resolution uses DNS-over-HTTPS so the check behaves the same in a container with no resolver
configured.
"""

import logging
import re
import secrets
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

DOH_ENDPOINT = "https://dns.google/resolve"
VERIFICATION_PREFIX = "_brim-verify"

_DOMAIN_RE = re.compile(
    r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)

# Per-process cache of verified origins, so a CORS check does not query the database per request.
_ORIGIN_CACHE: Dict[str, tuple[bool, float]] = {}
_ORIGIN_TTL_SECONDS = 60


def new_token() -> str:
    return f"brim-verify-{secrets.token_hex(12)}"


def normalise_domain(raw: Optional[str]) -> Optional[str]:
    """Accept what people paste — a URL, a host, or a host with a path — and keep the hostname."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if "://" not in text:
        text = f"https://{text}"
    parsed = urlparse(text)
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return None
    if not _DOMAIN_RE.match(host):
        raise ValueError("That does not look like a domain name, e.g. chat.example.com")
    return host


def _doh(name: str, record_type: str) -> List[str]:
    """Answers for a DNS name, as strings. Empty list on any failure — callers treat that as 'not yet'."""
    try:
        with httpx.Client(timeout=6.0) as client:
            response = client.get(
                DOH_ENDPOINT,
                params={"name": name, "type": record_type},
                headers={"accept": "application/dns-json"},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001 - DNS is best effort, never fatal
        logger.warning(f"DNS lookup failed for {name} ({record_type}): {exc}")
        return []

    answers = payload.get("Answer") or []
    return [str(answer.get("data", "")).strip().strip('"') for answer in answers]


def verify(
    domain: str,
    token: Optional[str],
    expected_host: Optional[str],
) -> Dict[str, object]:
    """Run both checks and report what was actually observed."""
    checks: List[Dict[str, object]] = []

    if token:
        txt_name = f"{VERIFICATION_PREFIX}.{domain}"
        txt_values = _doh(txt_name, "TXT")
        matched = any(token in value for value in txt_values)
        checks.append({
            "type": "TXT",
            "name": txt_name,
            "expected": token,
            "observed": txt_values,
            "passed": matched,
        })

    if expected_host:
        cname_values = _doh(domain, "CNAME")
        normalised = [value.rstrip(".").lower() for value in cname_values]
        matched = any(value == expected_host.lower() or value.endswith("." + expected_host.lower())
                      for value in normalised)
        checks.append({
            "type": "CNAME",
            "name": domain,
            "expected": expected_host,
            "observed": cname_values,
            "passed": matched,
        })

    passed = any(check["passed"] for check in checks)
    return {"verified": passed, "checks": checks}


def instructions(domain: str, token: Optional[str], expected_host: Optional[str]) -> List[Dict[str, str]]:
    """What to publish, in the order the company should try it."""
    rows = []
    if token:
        rows.append({
            "step": "1. Prove ownership (TXT)",
            "type": "TXT",
            "host": f"{VERIFICATION_PREFIX}.{domain}",
            "value": token,
            "note": "Add this at your DNS provider. It does not affect your website.",
        })
    if expected_host:
        rows.append({
            "step": "2. Point the domain at the app (CNAME)",
            "type": "CNAME",
            "host": domain,
            "value": expected_host,
            "note": "Add this where the domain's DNS is managed. The domain stays in your name.",
        })
    rows.append({
        "step": "3. Verify",
        "type": "-",
        "host": "-",
        "value": "-",
        "note": "Press Verify once the records have propagated (usually a few minutes).",
    })
    return rows


def is_verified_origin(origin: str, db_lookup) -> bool:
    """True when an Origin header belongs to one of the verified custom domains.

    ``db_lookup`` is a callable ``(host) -> bool`` supplied by the caller so this module does not
    import the database (and the middleware stays testable).
    """
    if not origin:
        return False
    host = urlparse(origin if "://" in origin else f"https://{origin}").hostname
    if not host:
        return False
    host = host.lower()

    cached = _ORIGIN_CACHE.get(host)
    now = time.time()
    if cached and now - cached[1] < _ORIGIN_TTL_SECONDS:
        return cached[0]

    try:
        allowed = bool(db_lookup(host))
    except Exception as exc:  # noqa: BLE001 - never fail a request because the cache lookup failed
        logger.warning(f"Custom-domain origin lookup failed for {host}: {exc}")
        allowed = False

    _ORIGIN_CACHE[host] = (allowed, now)
    return allowed


def clear_origin_cache() -> None:
    _ORIGIN_CACHE.clear()
