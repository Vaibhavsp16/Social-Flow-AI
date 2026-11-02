import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
API = "/api"

suffix = uuid.uuid4().hex[:6]
token = client.post(
    f"{API}/auth/signup",
    json={"name": "CB", "email": f"cb_{suffix}@brimtest.com", "password": "Cb@12345"},
).json()["access_token"]
h = {"Authorization": f"Bearer {token}"}
project = client.post(f"{API}/projects", json={"name": "CB", "industry": "Real Estate"}, headers=h).json()
bot = client.post(f"{API}/bots", json={"project_id": project["id"], "name": "CB Bot", "status": "Live"}, headers=h).json()
convo = client.post(f"{API}/conversations", json={"bot_id": bot["id"]}, headers=h).json()

for msg in [
    "I'm looking to buy a 3 BHK apartment in Ambli, budget around 2 crore",
    "can someone call me?",
]:
    data = client.post(f"{API}/conversations/{convo['id']}/messages", json={"message": msg}, headers=h).json()
    state = data.get("conversation_state", {})
    print(f"\n>> {msg}")
    print("   stage:", data.get("stage"), "| intent:", data.get("intent"))
    print("   lead_offered:", state.get("lead_offered"), "| lead_pending:", state.get("lead_pending"))
    print("   asked:", state.get("asked"))
    print("   reply:", data["reply"][:180])
