# app/api/auth.py

from datetime import datetime, timedelta, timezone
from typing import Annotated
import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt

from app.db.database import get_db
from app.db.models import User, UserRole

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Config ─────────────────────────────────────────────

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Schemas ────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: UserRole
    department: str = ""


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: UserRole
    department: str = ""


# ── Helpers ────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Dependencies ───────────────────────────────────────

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> User:
    """Decode JWT and return the User row, or raise 401."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exc
        user_id = int(user_id)
    except JWTError:
        raise credentials_exc

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exc
    return user


def require_role(*roles: UserRole):
    """Return a dependency that ensures the current user has one of the given roles."""
    def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' not allowed",
            )
        return user
    return _check


# ── Routes ─────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        password_hash=_hash_password(body.password),
        role=body.role,
        department=body.department or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not _verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "name": user.name, "email": user.email, "role": user.role.value, "department": user.department or ""},
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
