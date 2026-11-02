import uuid

import httpx

API = "http://127.0.0.1:8000/api"
c = httpx.Client(timeout=120)
email = f"dbgbrowse_{uuid.uuid4().hex[:6]}@brimtest.com"
tok = c.post(f"{API}/auth/signup", json={"name": "D", "email": email, "password": "Dbg@12345"}).json()["access_token"]
h = {"Authorization": f"Bearer {tok}"}
p = c.post(f"{API}/projects", json={"name": "D", "industry": "Real Estate"}, headers=h).json()
b = c.post(f"{API}/bots", json={"project_id": p["id"], "name": "D Bot", "status": "Live"}, headers=h).json()
cv = c.post(f"{API}/conversations", json={"bot_id": b["id"]}, headers=h).json()
print("bot", b["id"], "convo", cv["id"])
r = c.post(f"{API}/conversations/{cv['id']}/messages", json={"message": "Just looking at what's available"}, headers=h)
print(r.status_code)
d = r.json()
print("intent", d.get("intent"), "stage", d.get("stage"), "props", len(d.get("properties", [])))
print("reply:", d.get("reply"))
print("state:", {k: v for k, v in d.get("conversation_state", {}).items() if k != "last_shortlist_full"})
