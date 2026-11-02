"""
Build test documents that reproduce the shapes real uploads take.

The three customer files referenced in the request are not present on this machine, so this
script recreates each shape with known ground-truth text:

  website_export.pdf   one word per line, as a browser "print to PDF" produces
  brochure_images.pdf  pages that are pure images with no text layer (needs OCR)
  plan_layout.pdf      mixed: text pages plus a drawing page with dimension labels
  positioning.docx     headings, tables and an embedded image containing text
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "_fixtures"
OUT.mkdir(exist_ok=True)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
]


def font(size: int, bold: bool = False):
    for path in ([r"C:\Windows\Fonts\arialbd.ttf"] if bold else []) + FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── 1. browser-export PDF: every word on its own line ─────────────────────────
def website_export() -> Path:
    path = OUT / "website_export.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    pages = [
        [
            "Prycoons - The Name Of Game",
            "Skip to content",
            "Browse Properties Why Us Trends Insights Services Contact Career",
            "Buying a home is confusing. We simplify it.",
            "100% Verified Properties",
            "Zero Brokerage",
            "Dedicated Relationship Manager",
            "Area and Price Guidance",
            "Negotiation Support",
            "Market Comparison",
        ],
        [
            "Services",
            "Property Advisory",
            "Home Loan Assistance",
            "Legal Verification",
            "Interior Consultation",
            "Rental Management",
            "We work only in Ahmedabad and Gandhinagar.",
        ],
        [
            "Trends and Insights",
            "Ahmedabad residential prices rose 11 percent year on year.",
            "Bopal and Shela recorded the highest enquiry volume.",
            "Contact",
            "Call 1800 200 3000 or write to hello@prycoons.com",
        ],
    ]
    for lines in pages:
        y = 800
        for line in lines:
            # One word per line, blank line between words: the exact artifact this PDF type has.
            for word in line.split():
                c.drawString(50, y, word)
                y -= 18
                if y < 60:
                    c.showPage()
                    y = 800
            y -= 12
        c.showPage()
    c.save()
    return path


# ── 2. image-only brochure: no text layer at all ──────────────────────────────
def brochure_images() -> Path:
    pages = [
        [
            "THE SIGNATURE",
            "SN BUILT PVT. LTD.",
            "Established 1996",
            "A commercial project at Radhanpur Road, Mehsana",
        ],
        [
            "PROJECT HIGHLIGHTS",
            "Basement mechanical parking",
            "Ground floor plus seven upper floors",
            "Two level podium landscape",
            "Carpet area from 4105.85 sq ft",
        ],
        [
            "AREA STATEMENT",
            "Carpet Area 4105.85 sq ft",
            "Built Up Area 5210.40 sq ft",
            "FSI Area 5480.00 sq ft",
            "Common Area 1104.55 sq ft",
        ],
        [
            "AMENITIES",
            "High speed elevators",
            "24x7 security and CCTV",
            "DG backup power",
            "Fire fighting system as per norms",
        ],
        [
            "PAYMENT PLAN",
            "10 percent on booking",
            "40 percent on agreement",
            "40 percent on slab completion",
            "10 percent on possession",
        ],
        [
            "LOCATION ADVANTAGES",
            "5 minutes from Mehsana bus depot",
            "12 minutes from Mehsana railway station",
            "Close to Radhanpur Road commercial belt",
        ],
        [
            "DISCLAIMER",
            "This brochure is for information only.",
            "Areas are indicative and subject to final measurement.",
        ],
    ]
    writer = PdfWriter()
    tmp_files = []
    for index, lines in enumerate(pages):
        image = Image.new("RGB", (1654, 2339), "white")
        draw = ImageDraw.Draw(image)
        y = 180
        for line in lines:
            draw.text((140, y), line, fill="black", font=font(52, bold=line.isupper()))
            y += 110
        draw.text((140, 2200), f"Page {index + 1}", fill="black", font=font(30))
        image_path = OUT / f"_page_{index}.png"
        image.save(image_path)
        tmp_files.append(image_path)

        page_pdf = OUT / f"_page_{index}.pdf"
        c = canvas.Canvas(str(page_pdf), pagesize=A4)
        c.drawImage(str(image_path), 0, 0, width=A4[0], height=A4[1])
        c.save()
        writer.append(str(page_pdf))

    path = OUT / "brochure_images.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)

    for tmp in tmp_files + list(OUT.glob("_page_*.pdf")):
        try:
            tmp.unlink()
        except OSError:
            pass
    return path


# ── 3. mixed PDF: text pages plus an image-only drawing page ──────────────────
def plan_layout() -> Path:
    writer = PdfWriter()

    text_pdf = OUT / "_plan_text.pdf"
    c = canvas.Canvas(str(text_pdf), pagesize=A4)
    c.drawString(
        50, 780, "Typical floor plan - The Signature, Mehsana. Floor to floor height 3.6 m."
    )
    c.drawString(
        50, 760, "Each floor has four units. Unit A and Unit B face the road, Unit C and D the courtyard."
    )
    c.save()
    writer.append(str(text_pdf))

    # The drawing: an image with dimension labels and no text layer.
    image = Image.new("RGB", (1654, 2339), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([(200, 400), (1450, 1500)], outline="black", width=6)
    labels = [
        (220, 380, "TYPICAL FLOOR PLAN"),
        (300, 700, "UNIT A  1285 SQ FT"),
        (900, 700, "UNIT B  1285 SQ FT"),
        (300, 1200, "UNIT C  1420 SQ FT"),
        (900, 1200, "UNIT D  1420 SQ FT"),
        (250, 1600, "3 MT WIDE RAMP TO BASEMENT"),
        (250, 1700, "LIFT LOBBY 6 MT WIDE"),
        (250, 1800, "PROVISION FOR 42 MECHANICAL CAR PARKS"),
    ]
    for x, y, label in labels:
        draw.text((x, y), label, fill="black", font=font(44))
    image_path = OUT / "_plan_draw.png"
    image.save(image_path)

    draw_pdf = OUT / "_plan_draw.pdf"
    c = canvas.Canvas(str(draw_pdf), pagesize=A4)
    c.drawImage(str(image_path), 0, 0, width=A4[0], height=A4[1])
    c.save()
    writer.append(str(draw_pdf))

    path = OUT / "plan_layout.pdf"
    with open(path, "wb") as handle:
        writer.write(handle)
    for tmp in (text_pdf, draw_pdf, image_path):
        try:
            tmp.unlink()
        except OSError:
            pass
    return path


# ── 4. DOCX with headings, a table and an embedded image ─────────────────────
def positioning_docx() -> Path:
    import docx
    from docx.shared import Inches

    document = docx.Document()
    document.add_heading("Prycoons Strategic Website & Positioning Presentation", level=0)
    document.add_heading("Why Prycoons?", level=1)
    document.add_paragraph("Buying a home is confusing. We simplify it.")
    for point in (
        "100% Verified Properties",
        "Zero Brokerage",
        "Dedicated Relationship Manager",
        "Area & Price Guidance",
        "Negotiation Support",
        "Market Comparison",
    ):
        document.add_paragraph(point, style="List Bullet")

    document.add_heading("The Positioning Shift", level=1)
    document.add_paragraph("Right now: Prycoons feels like a property listing platform.")
    document.add_paragraph("We need to become: A home-buying decision partner.")
    document.add_paragraph("Your Real Estate Friend")

    document.add_heading("Channel Priorities", level=1)
    table = document.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    header = table.rows[0].cells
    header[0].text = "Channel"
    header[1].text = "Budget Share"
    header[2].text = "Primary KPI"
    for channel, share, kpi in (
        ("Instagram", "40 percent", "Qualified enquiries"),
        ("Google Search", "35 percent", "Cost per lead"),
        ("WhatsApp", "25 percent", "Site visit bookings"),
    ):
        row = table.add_row().cells
        row[0].text = channel
        row[1].text = share
        row[2].text = kpi

    document.add_heading("Site Visit Journey", level=1)
    image = Image.new("RGB", (1200, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 250), "ENQUIRY - SHORTLIST - SITE VISIT - BOOKING", fill="black", font=font(46))
    image_path = OUT / "_journey.png"
    image.save(image_path)
    document.add_picture(str(image_path), width=Inches(6))

    path = OUT / "positioning.docx"
    document.save(str(path))
    try:
        image_path.unlink()
    except OSError:
        pass
    return path


if __name__ == "__main__":
    for builder in (website_export, brochure_images, plan_layout, positioning_docx):
        created = builder()
        print(created.name, created.stat().st_size, "bytes")
