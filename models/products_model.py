from pydantic import BaseModel, RootModel
from typing import List


class Review(BaseModel):
    user_id: int
    rating: float
    comment: str
    created_at: str
    updated_at: str | None = None


class Variant(BaseModel):
    sku: str
    name: str
    additional_price: float | None = None
    attributes: dict = {}


class Price(BaseModel):
    amount: float
    currency: str = "USD"
    discount_percentage: float | None = None
    discounted_amount: float | None = None


class Manufacturer(BaseModel):
    name: str | None = None
    address: str | None = None
    country: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website: str | None = None


class Product(BaseModel):
    id: str
    sku: str
    name: str
    description: str | None = None
    category: str
    brand: str | None = None

    price: Price
    stock_quantity: int = 0
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

    created_at: str | None = None
    updated_at: str | None = None


class ProductsList(RootModel[List[Product]]):
    pass
