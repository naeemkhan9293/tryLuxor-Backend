from pydantic import BaseModel


class Address(BaseModel):
    street: str
    city: str
    state: str | None = None
    postal_code: str
    country: str


class User(BaseModel):
    id: int
    username: str
    email: str
    hashed_password: str
    full_name: str | None = None
    phone_number: str | None = None
    is_active: bool = True
    roles: list[str] = ["customer"]
    preferences: dict | None = None
    last_login: str | None = None

    addresses: list[Address] = []

    created_at: str | None = None
    updated_at: str | None = None
