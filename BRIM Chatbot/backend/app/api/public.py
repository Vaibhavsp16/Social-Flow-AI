"""Public surface: the shareable chatbot page, the embeddable widget and custom domains.

Nothing here requires a login — that is the point. Everything that could leak another tenant's data
is resolved through the bot's public slug or its verified domain.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.database.session import get_db
from app.models.bot import Bot
from app.models.project import Project
from app.models.user import User
from app.schemas.bot import DomainStatus, DomainUpdate
from app.services import domain_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Public"])


# ── Public bot metadata ───────────────────────────────────────────────────────

def _public_bot_payload(bot: Bot, project: Optional[Project]) -> dict:
    return {
        "id": bot.id,
        "name": bot.name,
        "description": bot.description,
        "language": bot.language,
        "slug": bot.shareable_slug,
        "status": bot.status,
        "company_name": bot.company_name or (project.name if project else None),
        "industry": project.industry if project else None,
        "greeting_preview": bot.greeting_preview,
        "primary_use_case": bot.primary_use_case,
        "idle_prompt_seconds": bot.idle_prompt_seconds,
        "lead_collection": bot.lead_collection,
        "contact_after_messages": bot.contact_after_messages,
        "custom_domain": bot.custom_domain,
    }


@router.get("/public/bots/{slug}")
def get_public_bot(slug: str, db: Session = Depends(get_db)):
    """Everything the public chat page needs, and nothing else."""
    bot = db.query(Bot).filter(Bot.shareable_slug == slug).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found.")
    if (bot.status or "").lower() != "live":
        raise HTTPException(
            status_code=403,
            detail="This chatbot is not published yet.",
        )
    project = db.query(Project).filter(Project.id == bot.project_id).first()
    return _public_bot_payload(bot, project)


@router.get("/public/resolve")
def resolve_domain(host: str, db: Session = Depends(get_db)):
    """Map a custom hostname to its bot, so a custom domain can open the right chat.

    Returns 404 when the host is not attached to any bot. Used by the app when it is served from a
    domain rather than a /p/{slug} path.
    """
    normalised = domain_service.normalise_domain(host)
    if not normalised:
        raise HTTPException(status_code=422, detail="Invalid host.")
    bot = db.query(Bot).filter(Bot.custom_domain == normalised).first()
    if not bot:
        raise HTTPException(status_code=404, detail="No chatbot is configured for this domain.")
    if (bot.domain_status or "none") != "verified":
        raise HTTPException(status_code=409, detail="This domain is not verified yet.")
    project = db.query(Project).filter(Project.id == bot.project_id).first()
    return _public_bot_payload(bot, project)


# ── Embeddable widget ────────────────────────────────────────────────────────

_WIDGET_TEMPLATE = """
(function () {
  var script = document.currentScript;
  if (!script) return;
  var slug = script.getAttribute('data-bot');
  if (!slug) { console.error('[BRIM] widget.js needs data-bot="<bot-slug>"'); return; }
  if (window.__brimWidgetLoaded && window.__brimWidgetLoaded[slug]) return;
  window.__brimWidgetLoaded = window.__brimWidgetLoaded || {};
  window.__brimWidgetLoaded[slug] = true;

  var apiBase = (script.getAttribute('data-api') || '__API_BASE__').replace(/\\/$/, '');
  var appBase = (script.getAttribute('data-host') || '__APP_BASE__').replace(/\\/$/, '');
  var title = script.getAttribute('data-title') || 'Chat with us';
  var accent = script.getAttribute('data-color') || '#6d4aff';

  var frameSrc = appBase + '/p/' + encodeURIComponent(slug) + '?embed=1&api=' + encodeURIComponent(apiBase);

  var root = document.createElement('div');
  root.setAttribute('data-brim-widget', slug);
  root.style.cssText = 'position:fixed;z-index:2147483000;right:20px;bottom:20px;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;';

  var panel = document.createElement('div');
  panel.style.cssText = 'position:absolute;right:0;bottom:74px;width:380px;max-width:calc(100vw - 32px);height:600px;max-height:calc(100vh - 120px);background:#fff;border-radius:16px;box-shadow:0 24px 60px rgba(17,17,27,.24);overflow:hidden;display:none;border:1px solid #e7e4f3;';

  var frame = document.createElement('iframe');
  frame.setAttribute('title', title);
  frame.setAttribute('allow', 'clipboard-write');
  frame.style.cssText = 'width:100%;height:100%;border:0;display:block;background:#fff;';

  var close = document.createElement('button');
  close.type = 'button';
  close.setAttribute('aria-label', 'Close chat');
  close.innerHTML = '&times;';
  close.style.cssText = 'position:absolute;top:8px;right:10px;width:28px;height:28px;border:0;border-radius:50%;background:rgba(255,255,255,.9);color:#4b5563;font-size:20px;line-height:1;cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.12);';

  var button = document.createElement('button');
  button.type = 'button';
  button.setAttribute('aria-label', title);
  button.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  button.style.cssText = 'width:56px;height:56px;border-radius:50%;border:0;background:' + accent + ';cursor:pointer;box-shadow:0 10px 24px rgba(109,74,255,.38);display:flex;align-items:center;justify-content:center;transition:transform .15s ease;';
  button.onmouseenter = function () { button.style.transform = 'scale(1.05)'; };
  button.onmouseleave = function () { button.style.transform = 'scale(1)'; };

  var open = false;
  function show() {
    open = true;
    if (!frame.getAttribute('src')) frame.setAttribute('src', frameSrc);
    panel.style.display = 'block';
    button.setAttribute('aria-expanded', 'true');
  }
  function hide() {
    open = false;
    panel.style.display = 'none';
    button.setAttribute('aria-expanded', 'false');
  }
  button.onclick = function () { open ? hide() : show(); };
  close.onclick = hide;
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && open) hide();
  });

  panel.appendChild(frame);
  panel.appendChild(close);
  root.appendChild(panel);
  root.appendChild(button);
  document.body.appendChild(root);
})();
"""


@router.get("/public/widget.js")
def widget_script(request: Request):
    """The embed script.

    A plain script tag is the whole integration: it adds a launcher bubble and frames the public
    chat page. No dependency on a CDN that may not exist, and the API/app origins are baked in from
    this deployment rather than hardcoded.
    """
    api_base = str(request.base_url).rstrip("/") + settings.API_V1_STR
    body = (
        _WIDGET_TEMPLATE
        .replace("__API_BASE__", api_base)
        .replace("__APP_BASE__", settings.frontend_url)
    )
    return Response(
        content=body,
        media_type="application/javascript; charset=utf-8",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── Custom domain management (owner only) ────────────────────────────────────

def _owned_bot(db: Session, bot_id: int, user: User) -> Bot:
    bot = (
        db.query(Bot)
        .join(Project, Project.id == Bot.project_id)
        .filter(Bot.id == bot_id, Project.user_id == user.id)
        .first()
    )
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found.")
    return bot


def _domain_payload(bot: Bot) -> dict:
    return {
        "domain": bot.custom_domain,
        "status": bot.domain_status or "none",
        "token": bot.domain_token,
        "checked_at": bot.domain_checked_at,
        "app_host": settings.app_host,
        "instructions": (
            domain_service.instructions(bot.custom_domain, bot.domain_token, settings.app_host)
            if bot.custom_domain else []
        ),
    }


@router.get("/bots/{bot_id}/domain", response_model=DomainStatus)
def get_domain(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _domain_payload(_owned_bot(db, bot_id, current_user))


@router.put("/bots/{bot_id}/domain", response_model=DomainStatus)
def set_domain(
    bot_id: int,
    payload: DomainUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Attach (or clear) a custom domain.

    The domain is only *recorded* here. Nothing is registered, transferred or charged: the company
    keeps the domain and its DNS, and proves control with a TXT record before it goes live.
    """
    bot = _owned_bot(db, bot_id, current_user)

    try:
        domain = domain_service.normalise_domain(payload.domain)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if domain is None:
        bot.custom_domain = None
        bot.domain_status = "none"
        bot.domain_token = None
        bot.domain_checked_at = None
        db.commit()
        domain_service.clear_origin_cache()
        return _domain_payload(bot)

    clash = (
        db.query(Bot)
        .filter(Bot.custom_domain == domain, Bot.id != bot.id)
        .first()
    )
    if clash:
        raise HTTPException(
            status_code=409, detail="That domain is already attached to another chatbot."
        )

    bot.custom_domain = domain
    bot.domain_status = "pending"
    # Keep the same token across edits so an already-published TXT record stays valid.
    bot.domain_token = bot.domain_token or domain_service.new_token()
    db.commit()
    db.refresh(bot)
    domain_service.clear_origin_cache()
    return _domain_payload(bot)


@router.post("/bots/{bot_id}/domain/verify", response_model=DomainStatus)
def verify_domain(
    bot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check the DNS records and record the outcome."""
    bot = _owned_bot(db, bot_id, current_user)
    if not bot.custom_domain:
        raise HTTPException(status_code=400, detail="Add a domain first.")

    result = domain_service.verify(
        bot.custom_domain, bot.domain_token, settings.app_host
    )
    from datetime import datetime, timezone

    bot.domain_status = "verified" if result["verified"] else "failed"
    bot.domain_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(bot)
    domain_service.clear_origin_cache()

    payload = _domain_payload(bot)
    payload["checks"] = result["checks"]
    return payload


@router.get("/public/bots/{slug}/embed-snippet")
def embed_snippet(slug: str, request: Request, db: Session = Depends(get_db)):
    """The exact snippet to paste, generated from this deployment's origins."""
    bot = db.query(Bot).filter(Bot.shareable_slug == slug).first()
    if not bot:
        raise HTTPException(status_code=404, detail="Chatbot not found.")

    api_base = str(request.base_url).rstrip("/") + settings.API_V1_STR
    script_src = f"{api_base}/public/widget.js"
    snippet = (
        f'<script src="{script_src}" data-bot="{slug}" async></script>'
    )
    iframe_src = f"{settings.frontend_url}/p/{slug}?embed=1"
    return {
        "slug": slug,
        "script_src": script_src,
        "snippet": snippet,
        "iframe": (
            f'<iframe src="{iframe_src}" title="{bot.name}" '
            'style="width:100%;height:640px;border:0;border-radius:12px"></iframe>'
        ),
        "public_url": f"{settings.frontend_url}/p/{slug}",
    }
