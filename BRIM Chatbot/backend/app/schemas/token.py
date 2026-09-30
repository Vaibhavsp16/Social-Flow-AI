from typing import Optional
from pydantic import BaseModel
from app.schemas.user import UserResponse

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None

class TokenPayload(BaseModel):
    sub: Optional[str] = None
