from enum import Enum

PREDEFINED_INDUSTRIES = [
    "Real Estate",
    "E-commerce",
    "Healthcare",
    "Education",
    "Finance & Banking",
    "Travel & Hospitality",
    "Legal Services",
    "Technology & SaaS",
    "Manufacturing",
    "Automotive",
    "Marketing & Advertising",
    "Logistics & Supply Chain",
    "Food & Restaurant",
    "Fitness & Wellness",
    "Professional Services",
    "Other"
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
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_FILE_EXTENSIONS = ALLOWED_DOCUMENT_EXTENSIONS.union(ALLOWED_IMAGE_EXTENSIONS)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max
