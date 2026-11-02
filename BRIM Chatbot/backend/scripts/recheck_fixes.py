"""Re-check the four defects found in the Kalpataru demo run."""

import httpx

API = "http://127.0.0.1:8000/api"
client = httpx.Client(timeout=180.0)

login = client.post(
    f"{API}/auth/login",
    json={"email": "kalpataru_5df6f5@brimtest.com", "password": "Demo@12345"},
)
print("login", login.status_code)
token = login.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

bots = client.get(f"{API}/bots", headers=h).json()
bot = next(b for b in bots if "Kalpataru Property" in b["name"])
print("bot", bot["id"], bot["name"])

# 1. Greeting branding + custom welcome
convo = client.post(
    f"{API}/conversations",
    json={"bot_id": bot["id"], "language": "en", "city": "Mumbai", "local_hour": 10},
    headers=h,
).json()
greeting = convo["messages"][0]["content"]
print("\n[1] greeting:", greeting.replace("\n", " | ")[:220])
print("    prycoons?", "Prycoons" in greeting, "| custom welcome?", greeting.startswith("Hello! Ask me about"))

# 2. Knowledge question that used to be hijacked
club = client.post(
    f"{API}/conversations/{convo['id']}/messages",
    json={"message": "What are the clubhouse timings at Palm Grove Residency?"},
    headers=h,
).json()
print("\n[2] reply:", club["reply"][:240].replace("\n", " "))
print("    hijacked?", "bedrooms" in club["reply"].lower(), "| sources:", len(club.get("sources") or []))

# 3. Analytics endpoint
analytics = client.get(f"{API}/analytics/bots/{bot['id']}", headers=h)
print("\n[3] analytics:", analytics.status_code, "| has_data:", analytics.json().get("has_data") if analytics.status_code == 200 else "-")

# 4. Markdown leakage
print("\n[4] markdown in replies:", "**" in club["reply"] or "**" in greeting)
