"""
Create (or promote) the platform administrator account.

Run from backend/:  python scripts/seed_admin.py [email] [password]

Prints nothing sensitive beyond the email it created. The role column is the only difference
between an admin and a business account; all admin routes check it server-side.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import get_password_hash
from app.database.session import SessionLocal
from app.models.user import User

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "admin@brim.ai"
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else "Admin@12345"

db = SessionLocal()
try:
    user = db.query(User).filter(User.email == EMAIL).first()
    if user:
        user.role = "ADMIN"
        user.password_hash = get_password_hash(PASSWORD)
        db.commit()
        print(f"Promoted existing account to ADMIN: {EMAIL}")
    else:
        db.add(
            User(
                name="Platform Admin",
                email=EMAIL,
                password_hash=get_password_hash(PASSWORD),
                role="ADMIN",
            )
        )
        db.commit()
        print(f"Created ADMIN account: {EMAIL}")
finally:
    db.close()
