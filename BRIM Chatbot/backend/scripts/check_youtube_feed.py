import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.social_service import SocialService

posts = SocialService._youtube_posts("https://www.youtube.com/@NASA")
print("posts found:", len(posts))
for post in posts[:3]:
    print("-", (post.get("date") or "?"), "|", (post.get("caption") or "")[:110].replace("\n", " "))
    print("  hashtags:", post.get("hashtags")[:6])
