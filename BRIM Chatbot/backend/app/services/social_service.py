"""
Social media ingestion.

A pasted profile or post link has to become answerable knowledge, not just a stored URL. The
platforms differ in what they expose to a server-side request, so this module layers strategies
and records honestly which one produced the content:

1. A caption the user pasted alongside the link. Always available, always accurate.
2. An official API when credentials are configured (Instagram Graph / X / YouTube Data API).
3. Public page metadata: Open Graph, JSON-LD, and the YouTube player response.
4. A structured record carrying the link, so "where can I find you?" is still answerable.

Captions, hashtags and mentions are extracted from whichever of those produced text.
"""
import html as html_lib
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.net_guard import assert_safe_url

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Meta serves social preview metadata to known crawlers even when a browser UA gets a login wall.
CRAWLER_UA = "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)"

PLATFORM_HOSTS = (
    ("Instagram", ("instagram.com",)),
    ("LinkedIn", ("linkedin.com", "lnkd.in")),
    ("X (Twitter)", ("twitter.com", "x.com")),
    ("Facebook", ("facebook.com", "fb.com", "fb.watch")),
    ("YouTube", ("youtube.com", "youtu.be")),
    ("TikTok", ("tiktok.com",)),
    ("Pinterest", ("pinterest.",)),
    ("Threads", ("threads.net",)),
    ("GitHub", ("github.com",)),
)

HASHTAG_RE = re.compile(r"(?<![\w&])#([\w\u0900-\u097F\u0A80-\u0AFF]{2,40})", re.UNICODE)
MENTION_RE = re.compile(r"(?<![\w@])@([A-Za-z0-9._]{2,30})")


def detect_platform(url: str) -> str:
    host = (urlparse(url).netloc or url).lower()
    for platform, needles in PLATFORM_HOSTS:
        if any(needle in host for needle in needles):
            return platform
    return "Social Profile"


def extract_hashtags(text: str) -> List[str]:
    seen, tags = set(), []
    for tag in HASHTAG_RE.findall(text or ""):
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags


def extract_mentions(text: str) -> List[str]:
    seen, names = set(), []
    for name in MENTION_RE.findall(text or ""):
        key = name.lower()
        # "@media" style CSS at-rules and email fragments are not mentions.
        if key in {"media", "import", "keyframes", "supports", "font"}:
            continue
        if key not in seen:
            seen.add(key)
            names.append(name)
    return names


POST_SEPARATOR = re.compile(r"^\s*(?:-{3,}|={3,}|\*{3,})\s*$", re.MULTILINE)
NUMBERED_HEADING = re.compile(r"(?m)^\s*(?:post\s*)?\d{1,2}\s*[.)\]:-]\s+")


def parse_caption_posts(text: str) -> List[Dict[str, Any]]:
    """
    Split pasted text into individual posts.

    Instagram and TikTok refuse anonymous reads, so the owner pastes captions. A block
    separated by ---, ====== or numbered lines means several posts; anything else is one post.
    Each post keeps its own hashtags so a question about hashtags can answer with real ones.
    """
    body = (text or "").strip()
    if not body:
        return []

    blocks = [block.strip() for block in POST_SEPARATOR.split(body) if block.strip()]
    if len(blocks) <= 1:
        numbered = [part.strip() for part in NUMBERED_HEADING.split(body) if part.strip()]
        if len(numbered) > 1:
            blocks = numbered

    posts: List[Dict[str, Any]] = []
    for block in blocks[:20]:
        caption = block.strip()
        posts.append({"caption": caption, "hashtags": extract_hashtags(caption)})
    return posts


def _clean_caption(text: str) -> str:
    """Undo JSON string escapes and collapse the newlines platforms insert."""
    if not text:
        return ""
    text = text.replace("\\n", "\n").replace('\\"', '"').replace("\\/", "/")
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


class SocialService:
    """Fetches what a platform is willing to expose and turns it into knowledge text."""

    TIMEOUT = 25

    # ── public entry point ────────────────────────────────────────────────────
    @classmethod
    def ingest(
        cls,
        url: str,
        platform: Optional[str] = None,
        caption: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        resolved = platform if platform and platform != "Social Profile" else detect_platform(url)
        pasted_caption = _clean_caption(caption or "")

        profile: Dict[str, Any] = {
            "platform": resolved,
            "url": url,
            "caption": "",
            "hashtags": [],
            "mentions": [],
            "method": "link-only",
            "error": None,
        }

        if not pasted_caption:
            fetched, method, error = cls._fetch(url, resolved)
            if fetched:
                profile.update(fetched)
                profile["method"] = method
            if error:
                profile["error"] = error[:300]

        # Individual posts are what a visitor actually asks about ("what do they post",
        # "which hashtags do they use", "show me a sample caption"). One profile blob cannot
        # answer that well, so posts are collected as separate records.
        posts: List[Dict[str, Any]] = list(profile.get("post_items") or [])

        if pasted_caption:
            # A caption supplied by the business owner is authoritative.
            pasted_posts = parse_caption_posts(pasted_caption)
            posts.extend(pasted_posts)
            profile["caption"] = pasted_caption if len(pasted_posts) == 1 else ""
            profile["method"] = "pasted-caption" if profile["method"] == "link-only" else (
                profile["method"] + "+pasted-caption"
            )

        if not posts and profile.get("posts"):
            # Handlers that expose only a list of strings still become quoteable posts.
            posts = [{"caption": text} for text in profile["posts"]]

        profile["post_items"] = posts
        hashtag_counts: Dict[str, int] = {}
        for post in posts:
            post_hashtags = post.get("hashtags") or extract_hashtags(post.get("caption") or "")
            post["hashtags"] = list(dict.fromkeys(post_hashtags))
            for tag in post["hashtags"]:
                hashtag_counts[tag] = hashtag_counts.get(tag, 0) + 1
        profile["hashtag_counts"] = dict(
            sorted(hashtag_counts.items(), key=lambda item: item[1], reverse=True)
        )
        if posts:
            profile["method"] = (
                f"{profile['method']}+{len(posts)}-posts"
                if profile["method"] != "link-only"
                else f"{len(posts)}-posts"
            )

        # Mentions come from prose only; a handle inside the page title is the account itself.
        combined = " ".join(
            str(profile.get(field) or "") for field in ("caption", "description", "bio")
        )
        profile["hashtags"] = list(
            dict.fromkeys(profile.get("hashtags") or [] + extract_hashtags(combined))
        )
        own_handle = (
            str(profile.get("account_name") or "").lstrip("@").strip().lower()
            or url.rstrip("/").rsplit("/", 1)[-1].split("?")[0].lower()
        )
        profile["mentions"] = [
            handle
            for handle in dict.fromkeys(
                profile.get("mentions") or [] + extract_mentions(combined)
            )
            # The profile's own handle is not an account it tagged.
            if handle.lstrip("@").strip().lower() != own_handle
        ]

        if name:
            profile["account_name"] = name

        return cls.compose(profile), profile

    # ── text assembly ─────────────────────────────────────────────────────────
    @staticmethod
    def compose(profile: Dict[str, Any]) -> str:
        platform = profile.get("platform") or "Social"
        lines: List[str] = [
            f"{platform} profile for this business.",
            f"Platform: {platform}",
            f"URL: {profile.get('url')}",
        ]
        if profile.get("account_name"):
            lines.append(f"Account: {profile['account_name']}")
        if profile.get("title"):
            lines.append(f"Page title: {profile['title']}")
        if profile.get("bio"):
            lines.append(f"Profile bio: {profile['bio']}")
        if profile.get("description"):
            lines.append(f"Profile summary: {profile['description']}")
        if profile.get("caption"):
            lines.append(f"Post caption: {profile['caption']}")
        if profile.get("hashtags"):
            lines.append("Hashtags: " + ", ".join(f"#{tag}" for tag in profile["hashtags"]))
        if profile.get("mentions"):
            lines.append("Accounts tagged: " + ", ".join(f"@{tag}" for tag in profile["mentions"]))
        if profile.get("stats"):
            lines.append(f"Audience: {profile['stats']}")
        if profile.get("links"):
            lines.append("Links shared: " + ", ".join(profile["links"][:5]))

        posts = profile.get("post_items") or []
        if posts:
            lines.append(f"Number of posts on record: {len(posts)}")
            for index, post in enumerate(posts[:12], start=1):
                header = f"Post {index}"
                if post.get("date"):
                    header += f" ({post['date']})"
                lines.append(header)
                caption = (post.get("caption") or "").strip()
                if caption:
                    lines.append(f"Caption: {caption}")
                if post.get("hashtags"):
                    lines.append("Hashtags: " + " ".join(f"#{tag}" for tag in post["hashtags"]))
                if post.get("permalink"):
                    lines.append(f"Post link: {post['permalink']}")
                engagement = []
                if post.get("likes") is not None:
                    engagement.append(f"{post['likes']} likes")
                if post.get("comments") is not None:
                    engagement.append(f"{post['comments']} comments")
                if engagement:
                    lines.append("Engagement: " + ", ".join(engagement))

        counts = profile.get("hashtag_counts") or {}
        if counts:
            ranked = ", ".join(f"#{tag} ({count})" for tag, count in list(counts.items())[:15])
            lines.append(f"Hashtags used across posts, most frequent first: {ranked}")

        method = profile.get("method", "link-only")
        if method == "link-only":
            lines.append(
                "Note: this platform blocked automatic reading of the post, so only the link is "
                "stored. Paste the caption text when adding the link to make the content "
                "answerable, or configure the platform API token."
            )
        else:
            lines.append(f"Content source: {method}")
        return "\n".join(line for line in lines if str(line).strip())

    # ── post harvesting ───────────────────────────────────────────────────────

    GRAPH_VERSION = "v21.0"

    @classmethod
    def _graph(cls, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Call the Meta Graph API. Returns None when no token is configured."""
        token = os.getenv("META_ACCESS_TOKEN") or os.getenv("INSTAGRAM_ACCESS_TOKEN") or ""
        if not token:
            return None
        query = dict(params)
        query["access_token"] = token
        url = f"https://graph.facebook.com/{cls.GRAPH_VERSION}/{path.lstrip('/')}"
        try:
            assert_safe_url(url)
            with httpx.Client(timeout=cls.TIMEOUT, follow_redirects=True) as client:
                response = client.get(url, params=query)
            if response.status_code >= 400:
                logger.warning("Graph API %s -> %s %s", path, response.status_code, response.text[:200])
                return None
            return response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Graph API %s failed: %s", path, exc)
            return None

    @classmethod
    def _post_limit(cls) -> int:
        try:
            return max(1, min(int(os.getenv("SOCIAL_POST_LIMIT", "12")), 50))
        except ValueError:
            return 12

    @classmethod
    def _instagram_posts(cls) -> List[Dict[str, Any]]:
        """Recent media for the connected Instagram business account."""
        target = (os.getenv("INSTAGRAM_USER_ID") or "").strip() or "me"
        payload = cls._graph(
            f"{target}/media",
            {
                "fields": "caption,permalink,timestamp,like_count,comments_count,media_type",
                "limit": cls._post_limit(),
            },
        )
        posts: List[Dict[str, Any]] = []
        for item in (payload or {}).get("data", []) or []:
            caption = (item.get("caption") or "").strip()
            posts.append(
                {
                    "caption": caption,
                    "hashtags": extract_hashtags(caption),
                    "permalink": item.get("permalink"),
                    "date": (item.get("timestamp") or "")[:10],
                    "likes": item.get("like_count"),
                    "comments": item.get("comments_count"),
                }
            )
        return posts

    @classmethod
    def _facebook_posts(cls) -> List[Dict[str, Any]]:
        page_id = (os.getenv("FACEBOOK_PAGE_ID") or "").strip()
        if not page_id:
            return []
        payload = cls._graph(
            f"{page_id}/posts",
            {"fields": "message,permalink_url,created_time", "limit": cls._post_limit()},
        )
        posts: List[Dict[str, Any]] = []
        for item in (payload or {}).get("data", []) or []:
            caption = (item.get("message") or "").strip()
            posts.append(
                {
                    "caption": caption,
                    "hashtags": extract_hashtags(caption),
                    "permalink": item.get("permalink_url"),
                    "date": (item.get("created_time") or "")[:10],
                }
            )
        return posts

    @classmethod
    def _youtube_channel_id(cls, url: str) -> Optional[str]:
        direct = re.search(r"/channel/(UC[\w-]{20,})", url)
        if direct:
            return direct.group(1)
        html = cls._get(url) or ""
        # The canonical link and externalId are the channel itself; the first "channelId" in the
        # page often belongs to a recommended channel instead.
        for pattern in (
            r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{20,})"',
            r'"externalId":"(UC[\w-]{20,})"',
            r'<meta itemprop="identifier" content="(UC[\w-]{20,})"',
            r'"channelId":"(UC[\w-]{20,})"',
        ):
            found = re.search(pattern, html)
            if found:
                return found.group(1)
        return None

    @classmethod
    def _youtube_posts(cls, url: str) -> List[Dict[str, Any]]:
        """Recent uploads with their descriptions, from YouTube's public channel feed."""
        channel_id = cls._youtube_channel_id(url)
        if not channel_id:
            return []

        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        soup = None
        try:
            assert_safe_url(feed_url)
            with httpx.Client(timeout=cls.TIMEOUT, follow_redirects=True) as client:
                response = client.get(feed_url, headers={"User-Agent": BROWSER_UA})
            if response.status_code < 400 and "<entry>" in response.text:
                soup = BeautifulSoup(response.text, "xml")
        except Exception as exc:  # noqa: BLE001
            logger.warning("YouTube feed failed for %s: %s", channel_id, exc)

        # The public feed is unavailable on some networks, so read the channel page instead.
        if soup is None:
            return cls._youtube_posts_from_page(url)

        namespaces = {"yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}
        posts: List[Dict[str, Any]] = []
        for entry in soup.find_all("entry")[: cls._post_limit()]:
            title = (entry.find("title").get_text(strip=True) if entry.find("title") else "")
            description_tag = entry.find("media:description", namespaces)
            description = description_tag.get_text(" ", strip=True) if description_tag else ""
            published = entry.find("published")
            link_tag = entry.find("link")
            caption = f"{title}. {description}".strip() if description else title
            posts.append(
                {
                    "caption": caption[:1200],
                    "hashtags": extract_hashtags(description or title),
                    "permalink": link_tag.get("href") if link_tag else None,
                    "date": published.get_text(strip=True)[:10] if published else None,
                }
            )
        return posts

    @classmethod
    def _youtube_posts_from_page(cls, url: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Recent uploads scraped from the channel page, with each video's description."""
        try:
            html = cls._get(url) or ""
        except Exception as exc:  # noqa: BLE001
            logger.info("YouTube channel page failed: %s", exc)
            return []

        video_ids = []
        for match in re.findall(r'"videoId":"([\w-]{11})"', html):
            if match not in video_ids:
                video_ids.append(match)
        if not video_ids:
            return []

        posts: List[Dict[str, Any]] = []
        for video_id in video_ids[:limit]:
            watch = f"https://www.youtube.com/watch?v={video_id}"
            description = ""
            title = ""
            try:
                page = cls._get(watch) or ""
                found = re.search(r'"shortDescription":"(.*?)","', page, re.S)
                if found:
                    description = _clean_caption(found.group(1))
                title_match = re.search(r'<meta name="title" content="([^"]+)"', page)
                if title_match:
                    title = html_lib.unescape(title_match.group(1))
            except Exception:  # noqa: BLE001
                continue
            if not (title or description):
                continue
            caption = f"{title}. {description}".strip() if description else title
            posts.append(
                {
                    "caption": caption[:1200],
                    "hashtags": extract_hashtags(description or title),
                    "permalink": watch,
                }
            )
        return posts

    # ── fetching ──────────────────────────────────────────────────────────────
    @classmethod
    def _fetch(cls, url: str, platform: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        handler = {
            "YouTube": cls._youtube,
            "Instagram": cls._instagram,
            "Facebook": cls._facebook,
            "X (Twitter)": cls._x,
            "TikTok": cls._tiktok,
            "LinkedIn": cls._linkedin,
        }.get(platform, cls._generic_site)
        try:
            return handler(url)
        except Exception as exc:  # noqa: BLE001
            logger.info("Social fetch failed for %s (%s): %s", url, platform, exc)
            return {}, "link-only", f"{type(exc).__name__}: {exc}"

    @classmethod
    def _get(cls, url: str, user_agent: str = BROWSER_UA) -> Optional[str]:
        assert_safe_url(url)
        with httpx.Client(
            timeout=cls.TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            response = client.get(url)
        if response.status_code >= 400:
            raise ValueError(f"HTTP {response.status_code}")
        return response.text

    @classmethod
    def _youtube(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        data: Dict[str, Any] = {}
        method = "link-only"
        error = None

        try:
            oembed = json.loads(cls._get(
                "https://www.youtube.com/oembed?format=json&url=" + url
            ) or "{}")
            if oembed.get("title"):
                data["title"] = oembed["title"]
                method = "youtube-oembed"
            if oembed.get("author_name"):
                data["account_name"] = oembed["author_name"]
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

        # The watch page carries the full description, which is where hashtags and links live.
        try:
            html = cls._get(url) or ""
            match = re.search(r'"shortDescription":"(.*?)","', html, re.S)
            if match:
                description = _clean_caption(match.group(1))
                if description:
                    data["caption"] = description
                    method = "youtube-description"
            if not data.get("title"):
                meta = cls._meta(html)
                data.setdefault("title", meta.get("title") or "")
                data.setdefault("description", meta.get("description") or "")
        except Exception as exc:  # noqa: BLE001
            error = error or str(exc)

        # A channel feed gives recent uploads with descriptions and hashtags, no API key needed.
        if not cls._instagram_shortcode(url):
            try:
                channel_posts = cls._youtube_posts(url)
                if channel_posts:
                    data["post_items"] = channel_posts
                    method = "youtube-feed"
            except Exception as exc:  # noqa: BLE001
                error = error or str(exc)

        if not data:
            return {}, "link-only", error
        return data, method, error

    @classmethod
    def _instagram(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        data: Dict[str, Any] = {}

        # A connected business account is the only reliable way to read real captions.
        if not cls._instagram_shortcode(url):
            try:
                account_posts = cls._instagram_posts()
                if account_posts:
                    data["post_items"] = account_posts
                    return data, "instagram-graph-posts", None
            except Exception as exc:  # noqa: BLE001
                logger.info("Instagram media list failed: %s", exc)

        token = os.getenv("META_ACCESS_TOKEN")
        if token:
            try:
                payload = json.loads(
                    cls._get(
                        "https://graph.facebook.com/v19.0/instagram_oembed"
                        f"?url={url}&access_token={token}"
                    ) or "{}"
                )
                title = _clean_caption(payload.get("title") or "")
                if title:
                    data["caption"] = title
                    data["account_name"] = payload.get("author_name")
                    return data, "instagram-graph-api", None
            except Exception as exc:  # noqa: BLE001
                logger.info("Instagram Graph lookup failed: %s", exc)

        shortcode = cls._instagram_shortcode(url)
        if shortcode:
            # The public embed still renders the caption when it exists.
            for variant in (
                f"https://www.instagram.com/p/{shortcode}/embed/captioned/",
                f"https://www.instagram.com/p/{shortcode}/embed/",
            ):
                try:
                    html = cls._get(variant) or ""
                except Exception:  # noqa: BLE001
                    continue
                soup = BeautifulSoup(html, "html.parser")
                node = soup.select_one(".Caption") or soup.select_one("div.Caption")
                caption = _clean_caption(node.get_text(" ", strip=True)) if node else ""
                if caption:
                    data["caption"] = caption
                    meta = cls._meta(html)
                    data.setdefault("title", meta.get("title") or "")
                    return data, "instagram-embed", None

        try:
            html = cls._get(url, CRAWLER_UA) or ""
        except Exception as exc:  # noqa: BLE001
            return {}, "link-only", str(exc)

        meta = cls._meta(html)
        if meta.get("title"):
            data["title"] = meta["title"]
        if meta.get("description"):
            data["description"] = meta["description"]
        account = re.search(r'"username":"([^"]+)"', html)
        if account:
            data["account_name"] = account.group(1)
        captions = re.findall(r'"edge_media_to_caption":\{"edges":\[\{"node":\{"text":"(.{10,1500}?)"\}\}\]', html)
        if captions:
            data["caption"] = _clean_caption(captions[0])
            return data, "instagram-public-json", None

        if data:
            return data, "instagram-meta", None
        return {}, "link-only", "Instagram returned a login wall with no public metadata."

    @classmethod
    def _instagram_shortcode(cls, url: str) -> Optional[str]:
        match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]{5,20})", url)
        return match.group(1) if match else None

    @classmethod
    def _facebook(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        token = os.getenv("META_ACCESS_TOKEN")
        data: Dict[str, Any] = {}

        # Page posts carry the same captions and hashtags visitors ask about.
        try:
            page_posts = cls._facebook_posts()
            if page_posts:
                data["post_items"] = page_posts
                return data, "facebook-graph-posts", None
        except Exception as exc:  # noqa: BLE001
            logger.info("Facebook page posts failed: %s", exc)

        if token:
            try:
                payload = json.loads(
                    cls._get(
                        "https://graph.facebook.com/v19.0/oembed_page"
                        f"?url={url}&access_token={token}"
                    ) or "{}"
                )
                if payload.get("title"):
                    data["title"] = payload["title"]
                    if payload.get("author_name"):
                        data["account_name"] = payload["author_name"]
                    return data, "facebook-graph-api", None
            except Exception as exc:  # noqa: BLE001
                logger.info("Facebook Graph lookup failed: %s", exc)

        try:
            html = cls._get(url, CRAWLER_UA) or ""
        except Exception as exc:  # noqa: BLE001
            return {}, "link-only", str(exc)
        meta = cls._meta(html)
        data.update({k: v for k, v in meta.items() if v})
        if not data:
            return {}, "link-only", "Facebook returned no public metadata."
        return data, "facebook-meta", None

    @classmethod
    def _x(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        bearer = os.getenv("X_BEARER_TOKEN")
        if bearer:
            match = re.search(r"/status/(\d+)", url)
            if match:
                try:
                    assert_safe_url("https://api.twitter.com")
                    with httpx.Client(timeout=cls.TIMEOUT) as client:
                        response = client.get(
                            f"https://api.twitter.com/2/tweets/{match.group(1)}"
                            "?tweet.fields=text,entities,created_at",
                            headers={"Authorization": f"Bearer {bearer}"},
                        )
                    payload = response.json()
                    text = (payload.get("data") or {}).get("text")
                    if text:
                        return {"caption": _clean_caption(text)}, "x-api", None
                except Exception as exc:  # noqa: BLE001
                    logger.info("X API lookup failed: %s", exc)

        try:
            html = cls._get(url, CRAWLER_UA) or ""
        except Exception as exc:  # noqa: BLE001
            return {}, "link-only", str(exc)
        meta = cls._meta(html)
        if meta:
            return meta, "x-meta", None
        return {}, "link-only", "X returned a login wall with no public metadata."

    @classmethod
    def _tiktok(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        try:
            payload = json.loads(
                cls._get("https://www.tiktok.com/oembed?url=" + url) or "{}"
            )
        except Exception as exc:  # noqa: BLE001
            return {}, "link-only", str(exc)
        data: Dict[str, Any] = {}
        if payload.get("title"):
            data["caption"] = _clean_caption(payload["title"])
        if payload.get("author_name"):
            data["account_name"] = payload["author_name"]
        if not data:
            return {}, "link-only", "TikTok returned no public metadata."
        return data, "tiktok-oembed", None

    @classmethod
    def _linkedin(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        html = cls._get(url) or ""
        meta = cls._meta(html)
        if not meta:
            return {}, "link-only", "LinkedIn returned no public metadata."
        # LinkedIn's own page text is mostly navigation; the description is the useful part.
        return meta, "linkedin-meta", None

    @classmethod
    def _generic_site(cls, url: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        html = cls._get(url) or ""
        meta = cls._meta(html, include_body=True)
        if not meta:
            return {}, "link-only", "No readable content at that URL."
        return meta, "page-metadata", None

    # ── metadata parsing ──────────────────────────────────────────────────────
    # Login walls and app banners that every social page repeats. They are not knowledge and
    # they crowd out the real description in the context window.
    CHROME_PATTERNS = re.compile(
        r"(log in|log in to .*|sign up|sign in|open app|use the app|see full profile|"
        r"get the full experience|agree & join|join now|skip to main content|"
        r"by clicking continue|cookie policy|privacy policy|forgot password|"
        r"don't have an account|already have an account)",
        re.IGNORECASE,
    )

    @staticmethod
    def _strip_chrome(text: str) -> str:
        if not text:
            return ""
        kept = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            cleaned = sentence.strip(" ·|•")
            if not cleaned or len(cleaned) < 12:
                continue
            if SocialService.CHROME_PATTERNS.search(cleaned):
                continue
            kept.append(cleaned)
        return " ".join(kept)

    @staticmethod
    def _meta(html: str, include_body: bool = False) -> Dict[str, Any]:
        """
        Open Graph, JSON-LD and (optionally) visible text, in that order of trust.

        ``include_body`` is off for social platforms: their visible text is mostly login
        prompts, while their Open Graph description is the profile summary a visitor cares
        about.
        """
        if not html:
            return {}
        soup = BeautifulSoup(html, "html.parser")
        data: Dict[str, Any] = {}

        def meta_content(*names: str) -> str:
            for name in names:
                tag = soup.find("meta", attrs={"property": name}) or soup.find(
                    "meta", attrs={"name": name}
                )
                if tag and tag.get("content"):
                    return _clean_caption(html_lib.unescape(tag["content"]))
            return ""

        data["title"] = meta_content("og:title", "twitter:title") or (
            soup.title.get_text(strip=True) if soup.title else ""
        )
        # og:description usually carries follower counts while the plain description carries the
        # bio ("Your Property Experts / 0 Brokerage…"). Take the richest one, not the first.
        candidates = [
            meta_content("og:description"),
            meta_content("twitter:description"),
            meta_content("description"),
        ]
        data["description"] = max((text for text in candidates if text), key=len, default="")

        for block in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = block.string or block.get_text() or ""
            if not raw.strip():
                continue
            try:
                parsed = json.loads(raw)
            except Exception:  # noqa: BLE001
                continue
            for node in parsed if isinstance(parsed, list) else [parsed]:
                if not isinstance(node, dict):
                    continue
                for key in ("headline", "name"):
                    if node.get(key) and not data.get("title"):
                        data["title"] = str(node[key]).strip()
                for key in ("articleBody", "description", "text"):
                    value = node.get(key)
                    if value and len(str(value)) > len(data.get("description", "")):
                        data["description"] = _clean_caption(str(value))

        data["description"] = SocialService._strip_chrome(data.get("description", ""))

        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        if include_body and len(data.get("description", "")) < 200:
            body_text = SocialService._strip_chrome(soup.get_text(" ", strip=True))
            if len(body_text) > len(data.get("description", "")):
                data["description"] = body_text[:4000]

        hashtags = extract_hashtags(" ".join(
            str(data.get(key) or "") for key in ("title", "description")
        ))
        if hashtags:
            data["hashtags"] = hashtags

        return {key: value for key, value in data.items() if value}
