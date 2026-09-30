from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin
from app.core.security import get_password_hash, verify_password, create_access_token

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
