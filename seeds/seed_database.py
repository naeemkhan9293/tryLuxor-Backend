from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from libs.database import Database
from models.products_model import Product, ProductsList
import os
from langchain_core.documents import Document
from pydantic import SecretStr
from pymongo.operations import SearchIndexModel
from langchain_mongodb import MongoDBAtlasVectorSearch
from libs.logger import get_logger

logger = get_logger(__name__)

api_key = SecretStr(str(os.getenv("GOOGLE_API_KEY")))
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    google_api_key=api_key,
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=api_key
)


async def create_search_index():
    logger.info("Creating search index...")
    try:
        db = Database.get_database()
        # Check if the collection exists before creating it
        if "products" not in await db.list_collection_names():
            await db.create_collection("products")

        collection = Database.get_collection("products")
        try:
            print("Dropping existing search index...")
            await collection.drop_search_index("vector_index")
        except Exception as e:
            print(f"Could not drop index 'vector_index' (it may not exist): {e}")

        search_index_model = SearchIndexModel(
            name="vector_index",
            type="vectorSearch",
            definition={
                "fields": [
                    {
                        "type": "vector",
                        "path": "embedding",
                        "numDimensions": 768,
                        "similarity": "cosine",
                    }
                ]
            },
        )
        collection = Database.get_sync_collection("products")
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=GoogleGenerativeAIEmbeddings(
                model="text-embedding-004", google_api_key=api_key
            ),
            type="vectorSearch",
            index_name="vector_index",
            relevance_score_fn="cosine",
        )

        logger.info("Successfully created search index")
        vector_store.create_vector_search_index(dimensions=768)
    except Exception as e:
        logger.error(f"Error creating search index: {e}")
        raise e


parser = PydanticOutputParser(pydantic_object=ProductsList)


async def generate_synthetic_data() -> list[Product]:
    logger.info("Generating synthetic data...")
    prompt = f"""
    You are a helpful assistant that generates synthetic data for a furniture store.
    You are to generate 20 products with the following fields:

    id: int
    sku: str (unique product code, like "SKU12345")
    name: str
    description: str
    category: str (e.g., "Furniture", "Electronics")
    brand: str
    price: object with:
        - amount: float
        - currency: str (e.g., "USD")
        - discount_percentage: float | null
        - discounted_amount: float | null
    stock_quantity: int
    in_stock: bool
    images: list of image URLs
    tags: list of strings (keywords)
    metadata: dict (any extra info)
    rating: float (average rating, 1-5)
    reviews: list of objects with:
        - user_id: int
        - rating: float
        - comment: str
        - created_at: str (ISO datetime)
    variants: list of objects with:
        - sku: str
        - name: str
        - additional_price: float | null
        - attributes: dict (e.g., {{"color": "red", "size": "M"}})
    manufacturer: object with:
        - name: str
        - address: str | null
        - country: str | null
        - contact_email: str | null
        - contact_phone: str | null
        - website: str | null
    weight: float | null (kg)
    dimensions: dict | null with:
        - length: float
        - width: float
        - height: float
    created_at: str (ISO datetime)
    updated_at: str (ISO datetime)

    {parser.get_format_instructions()}

    Return the data as a list of JSON objects.
    """
    print("Generating synthetic data...")
    response = llm.invoke(prompt)
    raw_output = response.content
    if isinstance(raw_output, list):
        raw_output = " ".join([str(part) for part in raw_output])

    parsed = parser.parse(str(raw_output))
    logger.info("Successfully created synthetic data...")
    return parsed.root


async def create_product_summary(product: Product) -> str:
    logger.info(f"creating product summary: {product.name}")
    manufacturer_details = (
        f"Made in {product.manufacturer.country}"
        if product.manufacturer and product.manufacturer.country
        else "Manufacturer information not available"
    )

    categories = ", ".join(product.tags) if product.tags else "No categories"
    reviews = (
        " ".join(
            [
                f"Rated {r.rating} on {r.created_at}: {r.comment}"
                for r in product.reviews
            ]
        )
        or "No reviews yet"
    )

    if product.price:
        base_price = f"{product.price.amount} {product.price.currency}"
        if product.price.discounted_amount:
            discount_info = f"Discounted: {product.price.discounted_amount} {product.price.currency}"
            if product.price.discount_percentage:
                discount_info += f" ({product.price.discount_percentage}% off)"
        else:
            discount_info = "No discounts available"
        price = f"Price: {base_price}. {discount_info}."
    else:
        price = "Price not available."

    summary = (
        f"{product.name} ({product.category}) by {product.brand or 'Unknown brand'}. "
        f"{manufacturer_details}. Categories: {categories}. "
        f"Reviews: {reviews}. {price}."
    )

    return summary


async def seed_database():
    logger.info(f"Seeding database...")
    try:
        collection = Database.get_collection("products")
        await create_search_index()
        synthetic_data: list[Product] = await generate_synthetic_data()

        records_with_summary = [
            Document(
                page_content=await create_product_summary(product),
                metadata=product.model_dump(),
            )
            for product in synthetic_data
        ]

        collection = Database.get_sync_collection("products")
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=GoogleGenerativeAIEmbeddings(
                model="text-embedding-004", google_api_key=api_key
            ),
            type="vectorSearch",
            index_name="vector_index",
            relevance_score_fn="cosine",
        )

        vector_store.add_documents(records_with_summary)

        # documents_to_insert = []
        # for record in records_with_summary:
        #     product_data = record.metadata.copy()  # Start with product's dict
        #     product_data["embedding_text"] = record.page_content
        #     product_data["embedding"] = embeddings.embed_query(record.page_content)
        #     documents_to_insert.append(product_data)

        # await collection.insert_many(documents_to_insert)

        # return JSONResponse(content={"data": [item.dict() for item in data]})
    except Exception as e:
        logger.error(f"Error seeding database: {e}")
        raise e
