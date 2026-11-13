from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.user import GoogleAuthRequest, UserCreate, UserLogin, UserResponse
from app.schemas.token import Token
from app.services.auth_service import AuthService
from app.models.user import User
from app.api.deps import get_current_user
from app.models.activity import ActivityType
from app.services.activity_service import log_activity

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
    log_activity(
        db, ActivityType.USER_SIGNUP.value,
        user_id=user.id, entity_type="user", entity_id=user.id,
    )
    db.commit()
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
    log_activity(
        db, ActivityType.USER_LOGIN.value,
        user_id=user.id, entity_type="user", entity_id=user.id,
    )
    db.commit()
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


# ── Google sign-in ────────────────────────────────────────────────────────────

@router.get("/google/config")
def google_config():
    """Tells the web app whether Google sign-in is usable, and which client id to use.

    Returned publicly because the browser needs it before anyone has a token. The client id is not
    a secret; it is visible in every page that renders the button.
    """
    from app.core.config import settings

    enabled = AuthService.google_enabled()
    return {
        "enabled": enabled,
        "client_id": settings.GOOGLE_CLIENT_ID or None,
        # Actionable rather than a bare false: whoever hits this needs to know which setting to set.
        "message": None if enabled else (
            "Google sign-in is off. Set GOOGLE_CLIENT_ID on the API and add this site's origin "
            "under Authorised JavaScript origins in Google Cloud Console."
        ),
    }


@router.post("/google", response_model=Token)
def google_signin(payload: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Sign in (or sign up) with a Google ID token.

    Same response shape as password login, so the client stores it identically.
    """
    user, token = AuthService.authenticate_google(db=db, credential=payload.credential)
    log_activity(
        db, ActivityType.USER_LOGIN.value,
        user_id=user.id, entity_type="user", entity_id=user.id,
        metadata={"provider": "google"},
    )
    db.commit()
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }
