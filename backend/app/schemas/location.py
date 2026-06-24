from pydantic import BaseModel

from app.schemas.base import TrackedRead


class LocationBase(BaseModel):
    name: str
    street1: str | None = None
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "US"
    phone: str | None = None
    website_url: str | None = None
    directions: str | None = None
    description: str | None = None
    distance_miles: float | None = None


class LocationUpdate(BaseModel):
    name: str | None = None
    street1: str | None = None
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone: str | None = None
    website_url: str | None = None
    directions: str | None = None
    description: str | None = None
    distance_miles: float | None = None


class LocationRead(LocationBase, TrackedRead):
    pass
