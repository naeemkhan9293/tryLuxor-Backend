from pydantic import BaseModel, RootModel, Field
from typing import List
from datetime import datetime, timezone

class Review(BaseModel):
    """A customer review for the product."""

    user_id: int
    rating: float
    comment: str
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc))


class Variant(BaseModel):
    """A specific variant of the product (e.g., Size, Color)."""

    sku: str
    name: str
    additional_price: float | None = None
    attributes: dict = {}


class Price(BaseModel):
    """Pricing information for the product."""

    amount: float
    currency: str = "USD"
    discount_percentage: float | None = None
    discounted_amount: float | None = None


class Manufacturer(BaseModel):
    """Information about the product's manufacturer."""

    name: str | None = None
    address: str | None = None
    country: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None


class Product(BaseModel):
    """The main product catalog model with automatic timestamps."""

    id: str
    sku: str
    name: str
    description: str | None = None
    category: str
    brand: str | None = None

    price: Price
    stock_quantity: int = 1
    in_stock: bool = True

    images: list[str] = []
    tags: list[str] = []
    metadata: dict | None = None

    rating: float | None = None
    reviews: list[Review] = []
    variants: list[Variant] = []

    manufacturer: Manufacturer | None = None

    weight: float | None = None
    dimensions: dict | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductsList(RootModel[List[Product]]):
    """A list wrapper for multiple products."""

    ...
