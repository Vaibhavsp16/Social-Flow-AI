"""Check multi-post caption parsing and the composed knowledge text."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services.social_service import SocialService, parse_caption_posts

BLOCK = """Our new 3 BHK show apartment at Prycoons Skyline in Bopal is open for visits. Book a slot
this weekend. #Prycoons #Bopal #3BHK #AhmedabadRealEstate
---
Monsoon offer: book before 30 November and save on stamp duty. Limited units left.
#Prycoons #Offer #Bopal #AhmedabadRealEstate
---
Meet the team behind Prycoons Skyline. 27 years of building homes in Ahmedabad.
#Prycoons #Team #RealEstate"""

posts = parse_caption_posts(BLOCK)
print("parsed posts:", len(posts))
for post in posts:
    print("  -", post["hashtags"])

text, profile = SocialService.ingest(
    "https://www.instagram.com/prycoons/",
    platform="Instagram",
    caption=BLOCK,
    name="Prycoons Instagram",
)
print()
print("method:", profile.get("method"))
print("hashtag_counts:", profile.get("hashtag_counts"))
print()
print(text)
