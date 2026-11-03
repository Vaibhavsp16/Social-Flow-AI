import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services.social_service import SocialService

text, profile = SocialService.ingest("https://www.instagram.com/prycoons/", platform="Instagram")
print("method:", profile.get("method"))
print("posts:", len(profile.get("post_items") or []))
print("account:", profile.get("account_name"))
print("---\n" + text)
