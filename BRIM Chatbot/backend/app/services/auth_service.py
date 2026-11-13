import logging
import secrets
from typing import Optional

import httpx
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User
from app.schemas.user import UserCreate, UserLogin
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token

logger = logging.getLogger(__name__)

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"

class AuthService:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email.lower().strip()).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_user(db: Session, user_in: UserCreate) -> User:
        existing_user = AuthService.get_user_by_email(db, user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists."
            )
        
        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            name=user_in.name.strip(),
            email=user_in.email.lower().strip(),
            password_hash=hashed_password,
            role=user_in.role or "BUSINESS"
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def authenticate_user(db: Session, user_in: UserLogin) -> tuple[User, str]:
        user = AuthService.get_user_by_email(db, user_in.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )
        if not verify_password(user_in.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )
        
        token = create_access_token(subject=str(user.id))
        return user, token

    # ── Google sign-in ───────────────────────────────────────────────────────

    @staticmethod
    def google_enabled() -> bool:
        return bool(settings.GOOGLE_CLIENT_ID)

    @staticmethod
    def verify_google_credential(credential: str) -> dict:
        """Validate a Google Identity Services ID token.

        The token arrives from the browser, so it is verified server-side against Google rather than
        decoded and trusted. ``aud`` must be our client id — otherwise a token minted for any other
        Google app would sign someone in here.
        """
        client_id = settings.GOOGLE_CLIENT_ID
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Google sign-in is not configured on this server. Set GOOGLE_CLIENT_ID on the "
                    "API and VITE_GOOGLE_CLIENT_ID on the web app."
                ),
            )
        if not credential or len(credential) > 8000:
            raise HTTPException(status_code=400, detail="Missing Google credential.")

        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(
                    GOOGLE_TOKENINFO_URL, params={"id_token": credential}
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Google token verification could not reach Google: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not reach Google to verify the sign-in. Please try again.",
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google sign-in could not be verified. Please try again.",
            )

        payload = response.json()
        if payload.get("aud") != client_id:
            logger.warning("Google token audience mismatch")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This Google sign-in is not valid for this application.",
            )
        if str(payload.get("email_verified", "")).lower() not in ("true", "1"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your Google email address is not verified.",
            )
        if not payload.get("email"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google did not return an email address.",
            )
        return payload

    @staticmethod
    def authenticate_google(db: Session, credential: str) -> tuple[User, str]:
        """Sign in with Google, creating the account on first use."""
        payload = AuthService.verify_google_credential(credential)

        google_id = str(payload.get("sub") or "").strip() or None
        email = str(payload["email"]).lower().strip()
        name = (payload.get("name") or email.split("@")[0]).strip()[:255]
        avatar = (payload.get("picture") or None)

        user: Optional[User] = None
        if google_id:
            user = db.query(User).filter(User.google_id == google_id).first()

        if user is None:
            user = AuthService.get_user_by_email(db, email)

        if user is None:
            # A Google-only account never gets a usable password. The hash is of a random secret
            # nobody holds, which also satisfies the NOT NULL column on databases created before
            # OAuth existed.
            user = User(
                name=name,
                email=email,
                password_hash=get_password_hash(secrets.token_urlsafe(32)),
                role="BUSINESS",
                google_id=google_id,
                avatar_url=avatar,
                auth_provider="google",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user, create_access_token(subject=str(user.id))

        # Existing account: link the Google identity, keep anything the user set themselves.
        changed = False
        if google_id and not user.google_id:
            user.google_id = google_id
            changed = True
        if avatar and user.avatar_url != avatar:
            user.avatar_url = avatar
            changed = True
        if not (user.name or "").strip() and name:
            user.name = name
            changed = True
        if changed:
            db.commit()
            db.refresh(user)

        return user, create_access_token(subject=str(user.id))
