"""End-to-end: a social handle must answer questions about posts, captions and hashtags."""
import httpx

A = "http://127.0.0.1:8000/api"
BOT_ID = 1380

CAPTIONS = """Handover day at Prycoons Skyline. Twelve families collected their keys this week.
#Prycoons #Bopal #Handover #AhmedabadRealEstate
---
Monsoon offer: book a 3 BHK at Skyline before 30 November and we cover the stamp duty.
Limited units. #Prycoons #Offer #3BHK #Bopal
---
Site progress update: tower A slab work is complete, tower B is on the ninth floor.
#Prycoons #Construction #Skyline #AhmedabadRealEstate
---
Meet the team behind 27 years of building homes in Ahmedabad. #Prycoons #Team #RealEstate"""

QUESTIONS = (
    "what is their social media handle?",
    "what are the hashtags they are using in their instagram?",
    "what do they post about on instagram?",
    "give me some sample captions from their posts",
)

client = httpx.Client(timeout=180)
token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

response = client.post(
    f"{A}/bots/{BOT_ID}/knowledge/social",
    headers=H,
    json={
        "url": "https://www.instagram.com/prycoons/",
        "platform": "Instagram",
        "name": "Prycoons Instagram",
        "caption": CAPTIONS,
    },
)
print("add social:", response.status_code, response.text[:160])
body = response.json()
print("chunks:", body.get("chunks_count"), "| status:", body.get("processing_status"))

convo = client.post(
    f"{A}/conversations", json={"bot_id": BOT_ID, "language": "en", "local_hour": 12}, headers=H
).json()

for question in QUESTIONS:
    reply = client.post(
        f"{A}/conversations/{convo['id']}/messages",
        json={"message": question},
        headers=H,
    ).json()
    print("\nQ:", question)
    print("A:", reply["reply"].replace("\n", " | ")[:700])
    print("sources:", len(reply.get("sources") or []), "| confidence:", reply.get("confidence"))
