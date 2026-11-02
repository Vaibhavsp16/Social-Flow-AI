"""
End-to-end document check against the running API.

Uploads each document shape, then asks questions whose answers are only in those documents and
prints the reply, citation count and confidence. A pass means the answer text contains the
expected fact.
"""
import os
import sys

import httpx

A = os.getenv("BRIM_API", "http://127.0.0.1:8000/api")
BOT_ID = int(os.getenv("BRIM_BOT_ID", "1380"))
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_fixtures")

client = httpx.Client(timeout=300)

token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

UPLOADS = [
    ("website_export.pdf", "Prycoons website export"),
    ("brochure_images.pdf", "Signature brochure (image-only)"),
    ("plan_layout.pdf", "Signature floor plan layout"),
    ("positioning.docx", "Prycoons positioning deck"),
    ("floor_plan.dxf", "Signature AutoCAD floor plan"),
]

SOCIAL = {
    "url": "https://www.instagram.com/p/C8xyzAbCdEf/",
    "platform": "Instagram",
    "name": "Prycoons launch post",
    "caption": (
        "Our new 3 BHK show apartment at Prycoons Skyline in Bopal is now open for site visits. "
        "Zero brokerage and a dedicated relationship manager for every family. "
        "#Prycoons #Bopal #AhmedabadRealEstate #3BHK @prycoons"
    ),
}

CASES = [
    ("What does the Instagram post about the show apartment say?", ["Bopal"]),
    ("Which hashtags are used in the Instagram post?", ["#Bopal", "#3BHK"]),
    ("Which marketing channel gets the biggest share and where is The Signature located?",
     ["Instagram", "Mehsana"]),
    ("Who is the developer and when was the company started?", ["SN Built", "1996"]),
    ("Where is The Signature project located?", ["Mehsana"]),
    ("What is the carpet area of the units?", ["4105.85"]),
    ("What is the payment plan?", ["10 percent", "booking"]),
    ("What is the floor to floor height on the typical floor?", ["3.6"]),
    ("How many mechanical car parks are provisioned in the basement?", ["42"]),
    ("Which channel gets the largest budget share?", ["Instagram", "40 percent"]),
    ("What is the site visit journey?", ["ENQUIRY", "BOOKING"]),
    ("What is the ramp width to the basement?", ["3 MT"]),
    ("What is the warranty on interstellar starships to Pluto?", ["__REFUSAL__"]),
]

print("Uploading documents to bot", BOT_ID)
source_ids = []
for filename, label in UPLOADS:
    path = os.path.join(BASE, filename)
    if not os.path.exists(path):
        print(f"  SKIP {filename} (missing)")
        continue
    with open(path, "rb") as handle:
        response = client.post(
            f"{A}/bots/{BOT_ID}/knowledge/upload",
            headers=H,
            files={"file": (filename, handle, "application/octet-stream")},
        )
    if response.status_code >= 400:
        print(f"  FAIL {filename}: {response.status_code} {response.text[:160]}")
        continue
    body = response.json()
    source_ids.append(body["id"])
    print(
        f"  {filename}: status={body.get('processing_status')} chunks={body.get('chunks_count')}"
    )

response = client.post(f"{A}/bots/{BOT_ID}/knowledge/social", headers=H, json=SOCIAL)
if response.status_code < 400:
    body = response.json()
    print(
        f"  social post: status={body.get('processing_status')} chunks={body.get('chunks_count')}"
    )
else:
    print("  social post FAILED:", response.status_code, response.text[:200])

convo = client.post(
    f"{A}/conversations", json={"bot_id": BOT_ID, "language": "en", "local_hour": 11}, headers=H
).json()
print("\nGreeting:", convo["messages"][0]["content"].replace("\n", " | "))

passed = 0
for question, expected in CASES:
    body = client.post(
        f"{A}/conversations/{convo['id']}/messages", json={"message": question}, headers=H
    ).json()
    reply = body["reply"]
    sources = len(body.get("sources") or [])
    if expected == ["__REFUSAL__"]:
        ok = "do not have enough information" in reply.lower() and sources == 0
    else:
        ok = all(fragment.lower() in reply.lower() for fragment in expected) and sources > 0
    passed += 1 if ok else 0
    print(f"\n[{'PASS' if ok else 'FAIL'}] {question}")
    print(f"   {reply[:220].replace(chr(10), ' ')}")
    print(f"   sources={sources} confidence={body.get('confidence')}")

print(f"\n{passed}/{len(CASES)} answered correctly")
print("source ids:", source_ids)
