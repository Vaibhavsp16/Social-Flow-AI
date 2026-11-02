"""
The eight industries BRIM positions itself in, and the knowledge pack that ships with each.

Each pack is the text of the matching brim.co.in industry page (crawled into
``demo_documents/brim/<key>.txt`` by ``scripts/build_industry_packs.py``). Seeding a pack gives
a bot the agency's positioning, service catalogue and FAQs for that industry, so a demo bot can
answer real questions without the presenter having to upload a document first.
"""

from typing import Dict, List, Optional

BRIM_INDUSTRY_PACKS: List[Dict[str, str]] = [
    {
        "key": "real-estate",
        "industry": "Real Estate",
        "name": "BRIM Real Estate Branding Playbook",
        "url": "https://brim.co.in/industry/real-estate/",
        "filename": "real-estate.txt",
        "description": "Project branding, RERA-ready collateral, site branding, digital lead generation and launch campaigns for developers.",
    },
    {
        "key": "fmcg",
        "industry": "FMCG",
        "name": "BRIM FMCG Branding Playbook",
        "url": "https://brim.co.in/industry/fmcg/",
        "filename": "fmcg.txt",
        "description": "Packaging, label and catalogue design, brand building, retail activation and national campaign rollout for FMCG products.",
    },
    {
        "key": "jewellery",
        "industry": "Jewellery",
        "name": "BRIM Jewellery Marketing Playbook",
        "url": "https://brim.co.in/industry/jewellery/",
        "filename": "jewellery.txt",
        "description": "Jewellery brand identity, seasonal campaigns, e-commerce, virtual try-on, influencer and in-store marketing.",
    },
    {
        "key": "education",
        "industry": "Education",
        "name": "BRIM Education Branding Playbook",
        "url": "https://brim.co.in/industry/education/",
        "filename": "education.txt",
        "description": "Institution branding, admission campaigns, campus collateral, student portals and digital marketing for schools and colleges.",
    },
    {
        "key": "healthcare",
        "industry": "Healthcare",
        "name": "BRIM Healthcare Branding Playbook",
        "url": "https://brim.co.in/industry/healthcare/",
        "filename": "healthcare.txt",
        "description": "Hospital and clinic branding, patient experience, appointment portals, telemedicine and compliant healthcare marketing.",
    },
    {
        "key": "food-and-hospitality",
        "industry": "Food & Hospitality",
        "name": "BRIM Food & Hospitality Playbook",
        "url": "https://brim.co.in/industry/food-and-hospitality/",
        "filename": "food-and-hospitality.txt",
        "description": "Restaurant branding, menu design, food photography, local SEO, booking systems and footfall campaigns.",
    },
    {
        "key": "engineering-and-manufacturing",
        "industry": "Engineering & Manufacturing",
        "name": "BRIM Engineering & Manufacturing Playbook",
        "url": "https://brim.co.in/industry/engineering-and-manufacturing/",
        "filename": "engineering-and-manufacturing.txt",
        "description": "Industrial brand identity, 3D product rendering, packaging, trade-show collateral and B2B digital marketing.",
    },
    {
        "key": "fashion",
        "industry": "Fashion",
        "name": "BRIM Fashion Branding Playbook",
        "url": "https://brim.co.in/industry/fashion/",
        "filename": "fashion.txt",
        "description": "Fashion label identity, lookbooks, influencer marketing, e-commerce storefronts and seasonal campaign creative.",
    },
]

PACKS_BY_KEY: Dict[str, Dict[str, str]] = {pack["key"]: pack for pack in BRIM_INDUSTRY_PACKS}

PACKS_BY_INDUSTRY: Dict[str, Dict[str, str]] = {
    pack["industry"]: pack for pack in BRIM_INDUSTRY_PACKS
}


def get_pack(key: Optional[str]) -> Optional[Dict[str, str]]:
    """Look a pack up by key ('real-estate') or by display industry name ('Real Estate')."""
    if not key:
        return None
    candidate = key.strip()
    return PACKS_BY_KEY.get(candidate) or PACKS_BY_INDUSTRY.get(candidate)
