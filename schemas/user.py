from pydantic import BaseModel
from typing import Optional


class UserBase(BaseModel):
    name: str
    email: str
    role: str = "operator"
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True