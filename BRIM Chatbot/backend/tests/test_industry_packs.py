import functools
import http.server
import threading
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient

from app.core.industry_packs import BRIM_INDUSTRY_PACKS
from app.main import app
from app.services.document_processor import DocumentProcessor

client = TestClient(app)


@pytest.fixture
def auth_headers():
    email = f"industry_{uuid.uuid4().hex[:8]}@example.com"
    res = client.post("/api/auth/signup", json={
        "name": "Industry Test User",
        "email": email,
        "password": "Password123!",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_bot(auth_headers):
    project = client.post("/api/projects", json={
        "name": f"BRIM Industry Project {uuid.uuid4().hex[:6]}",
        "industry": "Jewellery",
    }, headers=auth_headers).json()

    bot = client.post("/api/bots", json={
        "project_id": project["id"],
        "name": "BRIM Jewellery Assistant",
        "welcome_message": "Hello!",
    }, headers=auth_headers).json()
    return bot["id"]


def test_industry_pack_catalogue_covers_brim_industries():
    res = client.get("/api/knowledge/industry-packs")
    assert res.status_code == 200
    packs = res.json()
    assert len(packs) == 8

    industries = {pack["industry"] for pack in packs}
    assert industries == {
        "Real Estate", "FMCG", "Jewellery", "Education",
        "Healthcare", "Food & Hospitality",
        "Engineering & Manufacturing", "Fashion",
    }

    for pack in packs:
        assert pack["url"].startswith("https://brim.co.in/industry/")
        # Every pack must have a committed snapshot so seeding works offline.
        assert (Path("demo_documents") / "brim" / pack["filename"]).exists(), pack["filename"]


def test_seed_industry_pack_creates_searchable_knowledge(auth_headers, user_bot):
    res = client.post(
        f"/api/bots/{user_bot}/knowledge/seed-industry",
        json={"industry_key": "jewellery"},
        headers=auth_headers,
    )
    assert res.status_code == 201
    source = res.json()
    assert source["source_type"] == "DOCUMENT"
    assert source["processing_status"] == "COMPLETED"
    assert source["chunks_count"] >= 2
    assert source["source_url"] == "https://brim.co.in/industry/jewellery/"

    # The seeded content must actually be retrievable and cited.
    chat = client.post(
        f"/api/bots/{user_bot}/chat",
        json={"message": "What jewellery marketing services does BRIM offer?"},
        headers=auth_headers,
    )
    assert chat.status_code == 200
    body = chat.json()
    assert body["sources"], "expected citations from the seeded industry pack"
    assert body["sources"][0]["source_name"] == "BRIM Jewellery Marketing Playbook"


def test_seeding_same_pack_twice_refreshes_instead_of_duplicating(auth_headers, user_bot):
    for _ in range(2):
        res = client.post(
            f"/api/bots/{user_bot}/knowledge/seed-industry",
            json={"industry_key": "education"},
            headers=auth_headers,
        )
        assert res.status_code == 201

    sources = client.get(f"/api/bots/{user_bot}/knowledge", headers=auth_headers).json()
    education_sources = [s for s in sources if s["name"] == "BRIM Education Branding Playbook"]
    assert len(education_sources) == 1


def test_unknown_industry_pack_returns_404(auth_headers, user_bot):
    res = client.post(
        f"/api/bots/{user_bot}/knowledge/seed-industry",
        json={"industry_key": "space-tourism"},
        headers=auth_headers,
    )
    assert res.status_code == 404


@pytest.fixture
def static_site():
    """Two linked pages plus chrome, served locally so the crawl test stays offline."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "index.html").write_text(
            """
            <html><head><title>Seed Page Title</title></head>
            <body>
              <nav class="menu"><a href="/about">About</a></nav>
              <main>
                <h1>Seed page headline</h1>
                <p>BRIM builds real estate brands with launch campaigns and site branding.</p>
                <a href="/about.html">Our approach</a>
                <a href="https://external.example.com/page">External</a>
              </main>
              <footer>Copyright notice</footer>
            </body></html>
            """,
            encoding="utf-8",
        )
        (root / "about.html").write_text(
            """
            <html><head><title>About Page Title</title></head>
            <body><main><h1>About BRIM</h1>
            <p>We have served more than 200 clients across eight industries.</p>
            </main></body></html>
            """,
            encoding="utf-8",
        )

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            server.server_close()


@pytest.fixture
def allow_local_crawl(monkeypatch):
    """
    The static site these tests crawl runs on 127.0.0.1, which the SSRF guard blocks by design.
    The guard itself is covered in test_security.py; here the subject is extraction quality.
    """
    import app.services.document_processor as dp
    import app.services.knowledge_service as ks

    monkeypatch.setattr(dp, "assert_safe_url", lambda url: url)
    monkeypatch.setattr(ks, "assert_safe_url", lambda url: url)


def test_single_page_crawl_extracts_main_content(static_site, allow_local_crawl):
    text, metadata = DocumentProcessor.crawl_website(f"{static_site}/index.html", max_pages=1)
    assert metadata["pages_crawled"] == 1
    assert "launch campaigns" in text
    # Chrome must not leak into the knowledge base.
    assert "Copyright notice" not in text
    assert "About" not in text.split("Seed page headline")[0]


def test_multi_page_crawl_follows_internal_links_only(static_site, allow_local_crawl):
    text, metadata = DocumentProcessor.crawl_website(f"{static_site}/index.html", max_pages=5)
    pages = {page["url"] for page in metadata["pages"]}

    assert metadata["pages_crawled"] == 2
    assert any(url.endswith("/about.html") for url in pages)
    assert all("external.example.com" not in url for url in pages)
    assert "more than 200 clients" in text


def test_crawl_boundaries_reject_non_html_targets():
    from urllib.parse import urlparse

    base = urlparse("https://brim.co.in/industry/real-estate/")
    assert not DocumentProcessor._is_crawlable("https://brim.co.in/logo.png", base)
    assert not DocumentProcessor._is_crawlable("https://brim.co.in/wp-admin/admin.php", base)
    assert not DocumentProcessor._is_crawlable("https://other.com/page", base)
    assert DocumentProcessor._is_crawlable("https://brim.co.in/industry/fmcg/", base)


def test_website_endpoint_honours_max_pages(auth_headers, user_bot, static_site, allow_local_crawl):
    res = client.post(
        f"/api/bots/{user_bot}/knowledge/website",
        json={"url": f"{static_site}/index.html", "name": "Local Crawl", "max_pages": 5},
        headers=auth_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["processing_status"] == "COMPLETED"
    assert data["chunks_count"] >= 2

    detail = client.get(f"/api/knowledge/{data['id']}", headers=auth_headers).json()
    assert "more than 200 clients" in detail["extracted_text"]
