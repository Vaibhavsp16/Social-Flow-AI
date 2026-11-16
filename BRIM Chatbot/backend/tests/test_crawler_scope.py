"""Website ingestion must crawl the site, not just the URL that was typed.

Two regressions are pinned here, both of which produced a bot that could only talk about one
page:

* a seed on a sub-page crawled nothing else, because every link had to sit under the seed path;
* a site that redirects to ``www.`` rejected every link, because the host comparison was literal.
"""

import functools
import http.server
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import pytest

from app.services.document_processor import DocumentProcessor


def test_www_and_apex_are_the_same_site():
    base = urlparse("https://example.com/")
    assert DocumentProcessor._is_crawlable("https://www.example.com/about", base) is True
    assert DocumentProcessor._bare_host("www.example.com:443") == "example.com"
    # A genuinely different host is still rejected.
    assert DocumentProcessor._is_crawlable("https://cdn.example.net/about", base) is False


def test_siblings_are_crawlable_and_junk_is_not():
    base = urlparse("https://example.com/services/seo")
    # The old rule required /services/seo/... and returned False for all of these.
    assert DocumentProcessor._is_crawlable("https://example.com/about", base) is True
    assert DocumentProcessor._is_crawlable("https://example.com/products/gold", base) is True
    assert DocumentProcessor._is_junk_path("https://example.com/cart") is True
    assert DocumentProcessor._is_junk_path("https://example.com/privacy-policy") is True
    assert DocumentProcessor._is_junk_path("https://example.com/products/gold") is False


def test_links_are_ranked_with_seed_section_first():
    base = urlparse("https://example.com/services/seo")
    links = [
        "https://example.com/about",
        "https://example.com/services/seo/audit",
        "https://example.com/cart",
        "https://example.com/logo.png",
        "https://other.example.org/page",
    ]
    ranked = DocumentProcessor._rank_links(links, base)
    assert ranked[0] == "https://example.com/services/seo/audit"
    assert "https://example.com/cart" not in ranked
    assert "https://example.com/logo.png" not in ranked
    assert "https://other.example.org/page" not in ranked
    assert "https://example.com/about" in ranked


def test_meta_and_jsonld_rescue_a_javascript_shell():
    html = """
    <html><head>
      <title>Acme Jewellers</title>
      <meta name="description" content="Handmade gold and diamond jewellery since 1974.">
      <script type="application/ld+json">
        {"@type":"Store","name":"Acme Jewellers","description":"Bespoke bridal sets."}
      </script>
    </head><body><div id="root"></div></body></html>
    """
    page = DocumentProcessor._page_text(html, "https://acme.example/")
    assert "Handmade gold and diamond jewellery" in page["text"]
    assert "Bespoke bridal sets" in page["text"]


@pytest.fixture()
def multi_page_site():
    """A seed on a sub-page whose siblings are only reachable from the site nav."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "home.html").write_text(
            "<html><head><title>Home</title></head><body>"
            "<nav><a href='/home.html'>Home</a><a href='/products.html'>Products</a>"
            "<a href='/about.html'>About</a><a href='/cart'>Cart</a></nav>"
            "<main><p>Acme makes handmade gold jewellery in Rajkot. Established 1974.</p></main>"
            "</body></html>",
            encoding="utf-8",
        )
        (root / "products.html").write_text(
            "<html><head><title>Products</title></head><body><main>"
            "<a href='/products.html#gold'>Gold</a>"
            "<p>Handmade mangalsutra, kada and temple jewellery in 22 carat gold.</p>"
            "</main></body></html>",
            encoding="utf-8",
        )
        (root / "about.html").write_text(
            "<html><head><title>About</title></head><body><main>"
            "<p>Three generations of karigars, 14 showrooms across Gujarat.</p>"
            "</main></body></html>",
            encoding="utf-8",
        )

        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_seed_on_a_sub_page_still_crawls_the_site(multi_page_site, monkeypatch):
    from app.core import net_guard

    monkeypatch.setattr(net_guard, "_ALLOW_PRIVATE_FOR_TESTS", True, raising=False)
    monkeypatch.setattr(
        "app.services.document_processor.assert_safe_url", lambda url: url, raising=True
    )

    text, meta = DocumentProcessor.crawl_website(f"{multi_page_site}/home.html", max_pages=10)
    urls = {page["url"] for page in meta["pages"]}

    assert meta["pages_crawled"] >= 3, urls
    assert any("products.html" in url for url in urls)
    assert any("about.html" in url for url in urls)
    assert "handmade gold jewellery" in text.lower()
    assert "14 showrooms" in text
