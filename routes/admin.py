from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse
from libs.database import Database
from models.products_model import Product
from seeds.seed_database import create_product_summary
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
import os
from pydantic import SecretStr
from bson import ObjectId

router = APIRouter()

api_key = SecretStr(str(os.getenv("GOOGLE_API_KEY")))
embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=api_key
)

@router.post("/products")
async def create_product(product: Product):
    try:
        collection = Database.get_collection("products")
        
        product_summary = await create_product_summary(product)
        
        document = Document(
            page_content=product_summary,
            metadata=product.model_dump()
        )
        
        sync_collection = Database.get_sync_collection("products")
        vector_store = MongoDBAtlasVectorSearch(
            collection=sync_collection,
            embedding=embeddings,
            index_name="vector_index"
        )
        
        vector_store.add_documents([document])
        
        return JSONResponse(content={"message": "Product created successfully", "product_id": str(product.id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/products/{product_id}")
async def update_product(product_id: str, product: Product):
    try:
        sync_collection = Database.get_sync_collection("products")
        
        # Find the document's _id to delete it
        doc_to_delete = sync_collection.find_one({"metadata.id": product_id})
        if not doc_to_delete:
            raise HTTPException(status_code=404, detail="Product not found")

        # Delete the old document
        sync_collection.delete_one({"_id": doc_to_delete["_id"]})

        # Now, create and add the new document
        product_summary = await create_product_summary(product)
        
        document = Document(
            page_content=product_summary,
            metadata=product.model_dump()
        )
        
        vector_store = MongoDBAtlasVectorSearch(
            collection=sync_collection,
            embedding=embeddings,
            index_name="vector_index"
        )
        
        vector_store.add_documents([document])
        
        return JSONResponse(content={"message": "Product updated successfully", "product_id": str(product.id)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    try:
        sync_collection = Database.get_sync_collection("products")
        
        # Find the document's _id to delete it
        doc_to_delete = sync_collection.find_one({"metadata.id": product_id})
        if not doc_to_delete:
            raise HTTPException(status_code=404, detail="Product not found")

        result = sync_collection.delete_one({"_id": doc_to_delete["_id"]})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found during deletion")
            
        return JSONResponse(content={"message": "Product deleted successfully"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
