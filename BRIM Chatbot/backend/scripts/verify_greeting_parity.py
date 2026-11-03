"""The bot detail greeting and the chat's first message must be identical."""
import httpx

A = "http://127.0.0.1:8000/api"
client = httpx.Client(timeout=180)
token = client.post(
    f"{A}/auth/login", json={"email": "demo@brim.ai", "password": "Demo@12345"}
).json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

bots = client.get(f"{A}/bots", headers=H).json()
checked = 0
failures = 0

for bot in bots[:8]:
    bot_id = bot["id"]
    detail = client.get(f"{A}/bots/{bot_id}", headers=H).json()
    preview = (detail.get("greeting_preview") or "").strip()

    convo = client.post(
        f"{A}/conversations",
        json={"bot_id": bot_id, "language": "en", "local_hour": 11},
        headers=H,
    ).json()
    first = next(
        (m["content"] for m in convo.get("messages", []) if m.get("sender") == "ASSISTANT"),
        "",
    ).strip()

    matched = preview == first
    checked += 1
    failures += 0 if matched else 1
    print(f"[{'PASS' if matched else 'FAIL'}] bot {bot_id} {bot['name'][:28]!r}")
    print(f"       detail : {preview!r}")
    print(f"       chat   : {first!r}")

print(f"\n{checked - failures}/{checked} bots match")
