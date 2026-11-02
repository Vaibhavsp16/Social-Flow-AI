import httpx

A = "http://127.0.0.1:8000/api"
BOT_ID = 1380
client = httpx.Client(timeout=180)

token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

payload = {
    "url": "https://www.instagram.com/p/C8xyzAbCdEf/",
    "platform": "Instagram",
    "name": "Prycoons launch post",
    "caption": (
        "Our new 3 BHK show apartment at Prycoons Skyline in Bopal is now open for site visits. "
        "Zero brokerage and a dedicated relationship manager for every family. "
        "#Prycoons #Bopal #AhmedabadRealEstate #3BHK @prycoons"
    ),
}
r = client.post(f"{A}/bots/{BOT_ID}/knowledge/social", headers=H, json=payload)
print("create:", r.status_code, r.text[:300])
if r.status_code < 400:
    source = r.json()
    print("chunks:", source.get("chunks_count"), "status:", source.get("processing_status"))
    print("text:", (source.get("extracted_text") or "")[:400].replace("\n", " / "))

convo = client.post(
    f"{A}/conversations", json={"bot_id": BOT_ID, "language": "en", "local_hour": 11}, headers=H
).json()
for question in (
    "What does the Instagram post about the show apartment say?",
    "Which hashtags do you use on Instagram?",
    "Where can I find you on Instagram?",
):
    body = client.post(
        f"{A}/conversations/{convo['id']}/messages", json={"message": question}, headers=H
    ).json()
    print(f"\nQ: {question}\nA: {body['reply'][:240]}")
    print(f"   sources={len(body.get('sources') or [])} confidence={body.get('confidence')}")
