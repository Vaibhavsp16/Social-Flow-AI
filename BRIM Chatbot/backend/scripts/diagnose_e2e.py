"""
End-to-end diagnostic of the three demo paths: document upload, website crawl, RAG chat.
Run from backend/:  python scripts/diagnose_e2e.py
Creates its own account/project/bot and prints what the pipeline actually stored and answered.
"""

import io
import json
import time
import uuid
from pathlib import Path

import httpx
from docx import Document

API = "http://127.0.0.1:8000/api"
TMP = Path("_diag_tmp")
TMP.mkdir(exist_ok=True)

FACTS = {
    "fee": "The annual maintenance fee for Orion Tower is 42,500 rupees per apartment, payable quarterly.",
    "pool": "Orion Tower has a rooftop infinity pool on the 21st floor, open from 6 AM to 10 PM.",
    "parking": "Orion Tower provides two covered parking slots for every three-bedroom apartment.",
}


def build_docx() -> Path:
    doc = Document()
    doc.add_heading("Orion Tower Resident Handbook", level=1)
    doc.add_paragraph(
        "Orion Tower is a 24-storey residential building managed by Northwind Estates. "
        "It was completed in 2021 and houses 168 apartments."
    )
    doc.add_paragraph(FACTS["fee"])
    doc.add_paragraph(FACTS["pool"])
    doc.add_paragraph(FACTS["parking"])
    doc.add_paragraph(
        "Visitor parking is available in the basement level B2. Residents must register guests "
        "at the security desk before 9 PM."
    )
    path = TMP / "orion_handbook.docx"
    doc.save(path)
    return path


def build_txt() -> Path:
    path = TMP / "northwind_policy.txt"
    path.write_text(
        "Northwind Estates Policy Summary\n\n"
        "Complaints are acknowledged within 24 hours and resolved within 5 working days.\n"
        "The emergency maintenance helpline operates 24x7 at extension 1100.\n"
        "Residents may keep one pet per apartment, subject to society approval.\n",
        encoding="utf-8",
    )
    return path


def build_long_txt() -> Path:
    """~8k characters, with one fact buried in the middle, to prove chunking + retrieval."""
    filler = (
        "Residents are expected to keep common areas clean and to inform the management office "
        "about any damage to shared facilities. Requests for repairs are logged in the portal. "
    )
    parts = ["Northwind Estates Long-form Operations Manual\n"]
    for section in range(1, 21):
        parts.append(f"\nSection {section}: Daily Operations\n{filler * 3}\n")
        if section == 10:
            parts.append(
                "\nThe reserve fund contribution for Tower B is 3 percent of the annual budget.\n"
            )
    path = TMP / "operations_manual.txt"
    path.write_text("".join(parts), encoding="utf-8")
    return path


def build_png() -> Path:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (1000, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 40), "Harbour View Villas", fill="black")
    draw.text((20, 90), "Amenities: 9-hole golf course, valet parking,", fill="black")
    draw.text((20, 130), "private marina access and a clubhouse.", fill="black")
    path = TMP / "harbour_flyer.png"
    image.save(path)
    return path


def fetch_pdf() -> Path | None:
    url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        if response.status_code == 200 and response.content[:4] == b"%PDF":
            path = TMP / "dummy.pdf"
            path.write_bytes(response.content)
            return path
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] PDF download failed: {exc}")
    return None


def main() -> int:
    suffix = uuid.uuid4().hex[:8]
    email = f"diag_{suffix}@brimtest.com"
    client = httpx.Client(timeout=300.0)

    token = client.post(
        f"{API}/auth/signup",
        json={"name": "Diagnostics", "email": email, "password": "Diag@12345"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    project = client.post(
        f"{API}/projects",
        json={"name": f"Diagnostics {suffix}", "industry": "Real Estate"},
        headers=headers,
    ).json()
    bot = client.post(
        f"{API}/bots",
        json={"project_id": project["id"], "name": f"Diag Bot {suffix}", "status": "Live"},
        headers=headers,
    ).json()
    print(f"user={email} bot={bot['id']}")

    def upload(path: Path):
        with path.open("rb") as handle:
            response = client.post(
                f"{API}/bots/{bot['id']}/knowledge/upload",
                files={"file": (path.name, handle)},
                headers=headers,
            )
        body = response.json()
        print(
            f"upload {path.name}: {response.status_code} "
            f"{body.get('processing_status')} chunks={body.get('chunks_count')} "
            f"error={body.get('error_message')}"
        )
        text = body.get("extracted_text") or ""
        print(f"   text[:120]={text[:120]!r}")
        return body

    docx_body = upload(build_docx())
    txt_body = upload(build_txt())
    pdf_path = fetch_pdf()
    if pdf_path:
        upload(pdf_path)
    upload(build_png())
    upload(build_long_txt())

    started = time.time()
    site = client.post(
        f"{API}/bots/{bot['id']}/knowledge/website",
        json={"url": "https://brim.co.in/industry/real-estate/", "max_pages": 3},
        headers=headers,
    )
    site_body = site.json()
    meta = json.loads(site_body.get("metadata_json") or "{}")
    print(
        f"website: {site.status_code} {site_body.get('processing_status')} "
        f"chunks={site_body.get('chunks_count')} pages={meta.get('pages_crawled')} "
        f"chars={meta.get('character_count')} in {time.time() - started:.1f}s"
    )
    print(f"   pages={[p['url'] for p in meta.get('pages', [])]}")
    print(f"   text[:200]={(site_body.get('extracted_text') or '')[:200]!r}")

    questions = [
        ("DOCX detail", "What is the annual maintenance fee for Orion Tower?"),
        ("DOCX detail 2", "Which floor is the rooftop pool on and when does it open?"),
        ("TXT detail", "How quickly are complaints acknowledged by Northwind Estates?"),
        ("LONG DOC (middle)", "What is the reserve fund contribution for Tower B?"),
        ("IMAGE", "What amenities are available at Harbour View Villas?"),
        ("WEBSITE", "What services does BRIM offer for real estate brands?"),
        ("OVERVIEW", "What information do you have about this business?"),
        ("UNKNOWN", "What is the warranty policy on interstellar starships to Pluto?"),
    ]
    for label, question in questions:
        response = client.post(
            f"{API}/bots/{bot['id']}/chat", json={"message": question}, headers=headers
        )
        payload = response.json()
        sources = [f"{s['source_name']}:{round(s['similarity_score'], 3)}" for s in payload.get("sources", [])]
        print(f"\n[{label}] {question}")
        print(f"   -> {response.status_code} confidence={payload.get('confidence')} sources={sources}")
        print(f"   reply: {payload.get('reply', '')[:260]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
