from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse
from libs.database import Database
from models.products_model import ProductsList, Product

router = APIRouter()


@router.get("")
async def get_products():
    try:
        collection = Database.get_collection("products")
        raw_products = await collection.find().to_list(100)

        products_data = []
        for product_dict in raw_products:
            product_dict["id"] = str(product_dict["_id"])
            del product_dict["_id"]
            products_data.append(Product(**product_dict))

        products: ProductsList = ProductsList(products_data)
        return JSONResponse(content={"products": products.model_dump()})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
