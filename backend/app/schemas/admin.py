from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

Role = Literal["minister", "cos", "director_td", "liaison", "legal", "analyst", "data_coordinator", "admin"]


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    designation: str = Field(min_length=2, max_length=120)
    role: Role
    password: str = Field(min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def limit_bcrypt_input_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no more than 72 UTF-8 bytes")
        return value


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    designation: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    active: bool | None = None


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    email: EmailStr
    role: str
    designation: str
    active: bool
    created_at: datetime
