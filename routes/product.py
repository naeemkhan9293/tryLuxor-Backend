from fastapi import APIRouter, Depends, HTTPException, Query
from starlette.responses import JSONResponse
from libs.database import Database
from models.products_model import ProductsList, Product
from typing import Optional
import re

router = APIRouter()


def generate_slug(text: str) -> str:
    """Generate a URL-friendly slug from text."""
    slug = text.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


@router.get("")
async def get_products():
    try:
        collection = await Database.get_async_collection("products")
        raw_products = await collection.find().to_list(100)

        products_data = []
        for product_dict in raw_products:
            product_dict["id"] = str(product_dict["_id"])
            del product_dict["_id"]
            products_data.append(Product(**product_dict))

        products: ProductsList = ProductsList(products_data)
        return JSONResponse(content={"products": products.model_dump(mode='json')})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_products(
    limit: int = Query(default=20, ge=1, le=100, description="Number of products to return"),
    skip: int = Query(default=0, ge=0, description="Number of products to skip"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    brand: Optional[str] = Query(default=None, description="Filter by brand"),
    min_price: Optional[float] = Query(default=None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(default=None, ge=0, description="Maximum price"),
    in_stock: Optional[bool] = Query(default=None, description="Filter by stock availability"),
    search: Optional[str] = Query(default=None, description="Search in name and description"),
    sort_by: Optional[str] = Query(default="created_at", description="Sort field (name, price, rating, created_at)"),
    sort_order: Optional[str] = Query(default="desc", description="Sort order (asc or desc)"),
):
    """
    Search and filter products with various query parameters.

    Example: /products/search?category=Furniture&limit=10&min_price=100&max_price=500&in_stock=true
    """
    try:
        collection = await Database.get_async_collection("products")

        # Build filter query
        filter_query = {}

        if category:
            filter_query["category"] = {"$regex": category, "$options": "i"}

        if brand:
            filter_query["brand"] = {"$regex": brand, "$options": "i"}

        if min_price is not None or max_price is not None:
            price_filter = {}
            if min_price is not None:
                price_filter["$gte"] = min_price
            if max_price is not None:
                price_filter["$lte"] = max_price
            filter_query["price.amount"] = price_filter

        if in_stock is not None:
            filter_query["in_stock"] = in_stock

        if search:
            filter_query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"tags": {"$regex": search, "$options": "i"}},
            ]

        # Build sort query
        sort_field = sort_by
        if sort_by == "price":
            sort_field = "price.amount"

        sort_direction = -1 if sort_order == "desc" else 1

        # Execute query with pagination
        raw_products = await collection.find(filter_query).sort(sort_field, sort_direction).skip(skip).limit(limit).to_list(limit)

        # Get total count for pagination info
        total_count = await collection.count_documents(filter_query)

        products_data = []
        for product_dict in raw_products:
            product_dict["id"] = str(product_dict["_id"])
            del product_dict["_id"]
            products_data.append(Product(**product_dict))

        products: ProductsList = ProductsList(products_data)

        return JSONResponse(content={
            "products": products.model_dump(mode='json'),
            "pagination": {
                "total": total_count,
                "limit": limit,
                "skip": skip,
                "returned": len(products_data)
            }
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{slug}")
async def get_product_by_slug(slug: str):
    """
    Get a single product by its slug (generated from product name).

    Example: /products/modern-leather-sofa
    """
    try:
        collection = await Database.get_async_collection("products")

        # Find all products and match by generated slug
        raw_products = await collection.find().to_list(1000)

        for product_dict in raw_products:
            product_slug = generate_slug(product_dict.get("name", ""))

            if product_slug == slug:
                product_dict["id"] = str(product_dict["_id"])
                del product_dict["_id"]
                product = Product(**product_dict)
                return JSONResponse(content={"product": product.model_dump(mode='json')})

        raise HTTPException(status_code=404, detail="Product not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


