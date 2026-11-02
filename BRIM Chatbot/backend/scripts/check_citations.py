"""Confirm citation chips are unique per source and capped."""
import httpx

A = "http://127.0.0.1:8000/api"
client = httpx.Client(timeout=180)
token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

convo = client.post(
    f"{A}/conversations", json={"bot_id": 1380, "language": "en", "local_hour": 12}, headers=H
).json()

for question in (
    "Who is the developer and when was the company started?",
    "Which marketing channel gets the biggest share and where is The Signature located?",
    "What does the Instagram post about the show apartment say?",
):
    body = client.post(
        f"{A}/conversations/{convo['id']}/messages",
        json={"message": question},
        headers=H,
    ).json()
    names = [source["source_name"] for source in body["sources"]]
    print(question)
    print("  reply:", body["reply"][:100].replace("\n", " "))
    print("  chips:", names)
    print("  distinct:", len(set(names)), "| total:", len(names))
