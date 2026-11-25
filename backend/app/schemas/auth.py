from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class LoginResult(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic

