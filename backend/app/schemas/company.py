"""Company and membership schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import MembershipRole


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_list(value: list[str]) -> list[str]:
    cleaned: list[str] = []
    for item in value:
        text = item.strip()
        if text and text not in cleaned:
            if len(text) > 120:
                raise ValueError("Each entry must be 120 characters or fewer")
            cleaned.append(text)
    if len(cleaned) > 40:
        raise ValueError("Provide at most 40 entries")
    return cleaned


class CompanyWrite(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    industry: str | None = Field(default=None, max_length=200)
    website: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=8000)
    contact_email: str | None = Field(default=None, max_length=320)
    contact_phone: str | None = Field(default=None, max_length=50)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=120)
    services: list[str] = Field(default_factory=list)
    expertise: list[str] = Field(default_factory=list)
    brand_tagline: str | None = Field(default=None, max_length=300)
    brand_voice: str | None = Field(default=None, max_length=4000)
    brand_primary_color: str | None = Field(default=None, max_length=32)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("Company name is required")
        return stripped

    @field_validator(
        "industry",
        "website",
        "description",
        "contact_email",
        "contact_phone",
        "address_line1",
        "address_line2",
        "city",
        "region",
        "postal_code",
        "country",
        "brand_tagline",
        "brand_voice",
        "brand_primary_color",
    )
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("contact_email")
    @classmethod
    def lower_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.lower()

    @field_validator("services", "expertise")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return _clean_list(value)


class CompanyUpdate(CompanyWrite):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class CompanyResponse(BaseModel):
    id: UUID
    name: str
    industry: str | None
    website: str | None
    description: str | None
    contact_email: str | None
    contact_phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    country: str | None
    services: list[str]
    expertise: list[str]
    brand_tagline: str | None
    brand_voice: str | None
    brand_primary_color: str | None
    role: MembershipRole


class MemberCreate(BaseModel):
    email: EmailStr
    role: MembershipRole = MembershipRole.MEMBER

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class MemberRoleUpdate(BaseModel):
    role: MembershipRole


class MemberResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: MembershipRole
    created_at: datetime
