from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse
from libs.database import Database

router = APIRouter()


@router.get("")
async def get_products():
    try:
        collection = Database.get_collection("products")
        products = await collection.find().to_list(100)
        for product in products:
            product["_id"] = str(product["_id"])
        return JSONResponse(content={"products": products})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
