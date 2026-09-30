from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.services.auth_service import AuthService
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user, create their account and return an access token.
    """
    user = AuthService.create_user(db=db, user_in=user_in)
    _, token = AuthService.authenticate_user(
        db=db,
        user_in=UserLogin(email=user_in.email, password=user_in.password)
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user with email and password and return an access token.
    """
    user, token = AuthService.authenticate_user(db=db, user_in=user_in)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current logged in user details.
    """
    return current_user
