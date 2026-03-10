from pydantic import BaseModel, Field

from app.choices import RoleType


class TokenIssueRequest(BaseModel):
    userId: int
    role: RoleType = "user"
    ttlMinutes: int | None = Field(default=None, ge=1, le=1440)


class LoginRequest(BaseModel):
    userId: int
    password: str = Field(min_length=8, max_length=128)


class CredentialUpsertRequest(BaseModel):
    userId: int
    password: str = Field(min_length=8, max_length=128)
    role: RoleType = "user"


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresInSeconds: int


class MeResponse(BaseModel):
    userId: int | None
    role: str
    source: str
    privileged: bool


class CredentialResponse(BaseModel):
    userId: int
    role: RoleType
