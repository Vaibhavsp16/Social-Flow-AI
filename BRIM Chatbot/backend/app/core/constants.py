from enum import Enum

# The eight industries BRIM serves (https://brim.co.in/industry/), in site order. Each one has a
# matching knowledge pack in app/core/industry_packs.py, so the selected industry can seed the
# bot with agency content out of the box. "Other" stays last as an escape hatch.
PREDEFINED_INDUSTRIES = [
    "Real Estate",
    "FMCG",
    "Jewellery",
    "Education",
    "Healthcare",
    "Food & Hospitality",
    "Engineering & Manufacturing",
    "Fashion",
    "Other",
]

class UserRole(str, Enum):
    ADMIN = "ADMIN"
    BUSINESS = "BUSINESS"

class KnowledgeSourceType(str, Enum):
    DOCUMENT = "DOCUMENT"
    IMAGE = "IMAGE"
    WEBSITE = "WEBSITE"
    SOCIAL_LINK = "SOCIAL_LINK"
    INSTRUCTION = "INSTRUCTION"

class ProcessingStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

# File upload restrictions
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".dxf", ".dwg"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_FILE_EXTENSIONS = ALLOWED_DOCUMENT_EXTENSIONS.union(ALLOWED_IMAGE_EXTENSIONS)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max
