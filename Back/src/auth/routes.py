"""Rutas de autenticación: login, register, refresh, me."""
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from src.auth.models import User

# Configuración JWT
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 7))

# Password hashing - use sha256_crypt to avoid bcrypt 5.0.0 + passlib 1.7.4 compatibility issues
pwd_context = CryptContext(
    schemes=["sha256_crypt"],
    deprecated="auto",
    sha256_crypt__rounds=29000
)

router = APIRouter(prefix="/auth", tags=["autenticación"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Schemas ----------
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    role: str = "client"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------- Helpers ----------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado") from None
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido") from None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# ---------- Endpoints ----------

@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login con email y password (JSON)."""
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
    refresh_token = create_refresh_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        user=UserInfo(id=user.id, email=user.email, role=user.role, is_active=user.is_active)
    )


@router.post("/register", response_model=TokenResponse)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """Registra un nuevo usuario y devuelve tokens."""
    if get_user_by_email(db, data.email):
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    if data.role not in ("client", "admin"):
        raise HTTPException(status_code=400, detail="Rol inválido")
    hashed_pw = get_password_hash(data.password)
    user = User(email=data.email, hashed_password=hashed_pw, role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    access_token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
    refresh_token = create_refresh_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        user=UserInfo(id=user.id, email=user.email, role=user.role, is_active=user.is_active)
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    data: RefreshRequest,
    db: Session = Depends(get_db)
):
    """Refresca el access token usando un refresh token válido."""
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Token no es de tipo refresh")
    email = payload.get("sub")
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")
    access_token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
    new_refresh_token = create_refresh_token({"sub": user.email, "user_id": user.id})
    return TokenResponse(
        access_token=access_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=new_refresh_token,
        user=UserInfo(id=user.id, email=user.email, role=user.role, is_active=user.is_active)
    )


@router.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)):
    """Devuelve info del usuario autenticado."""
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active
    )
