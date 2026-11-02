import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.models.user import User
from app.services.reporting_service import ReportingService
from app.services.weather_service import WeatherService

for city in ("Ahmedabad", "Mumbai"):
    snap = WeatherService.get(city)
    print(city, "available=", snap["available"], "summary=", snap["summary"])

db = SessionLocal()
user = db.query(User).filter(User.email == "demo@brim.ai").first()
report = ReportingService.build(db, "conversations", user_id=user.id)
pdf = ReportingService.to_pdf(report)
print("report rows:", len(report["rows"]), "pdf bytes:", len(pdf), "header:", pdf[:5])
Path("_verify_tmp/report.pdf").write_bytes(pdf)
db.close()
