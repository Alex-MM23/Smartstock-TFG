"""Esquemas Pydantic compartidos para la API."""
from typing import Literal

from pydantic import BaseModel


class ProductResponse(BaseModel):
    id: int
    title: str
    price: float
    cantidad: int
    category: str | None = None
    image: str | None = None

    class Config:
        orm_mode = True


class OrderItemSchema(BaseModel):
    product_id: int
    quantity: int
    price: float


class OrderCreateSchema(BaseModel):
    user_id: int
    total_amount: float
    items: list[OrderItemSchema]


# ---------- Auth Schemas ----------
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    email: str
    role: Literal['client', 'admin']
    is_active: bool = True


class UserInfoResponse(BaseModel):
    id: int
    email: str
    role: Literal['client', 'admin']
    is_active: bool = True


class RegisterRequest(BaseModel):
    email: str
    password: str
    role: Literal['client', 'admin'] = 'client'
