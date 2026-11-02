import sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.models.bot import Bot
from app.models.project import Project
from app.models.user import User
from app.services.real_estate_flow import RealEstateFlow, extract_slots, KNOWN_AREAS

db = SessionLocal()
suffix = uuid.uuid4().hex[:6]
user = User(name="Dbg", email=f"dbg_{suffix}@brimtest.com", password_hash="x")
db.add(user)
db.commit()
project = Project(user_id=user.id, name="Dbg", industry="Real Estate")
db.add(project)
db.commit()
bot = Bot(project_id=project.id, name="Dbg Bot", status="Live")
db.add(bot)
db.commit()
convo = type("C", (), {"id": None})()

state = {}
msg = "Just looking at what's available"
print("slots:", extract_slots(msg, state))
out = RealEstateFlow.handle(db, bot, convo, msg, state)
print("stage:", out["stage"], "intent:", out["state"].get("intent"))
print("props:", len(out["properties"]))
print("reply:", out["reply"][:200])
print("state:", {k: v for k, v in out["state"].items() if k != "last_shortlist_full"})
db.close()
