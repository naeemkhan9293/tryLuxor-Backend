import uvicorn
from fastapi import FastAPI
from starlette.responses import JSONResponse
from routes import chat_route

app = FastAPI(debug=True)


app.include_router(chat_route.router, prefix="/chat")


@app.get("/")
async def read_root():
    return JSONResponse(content={"message": "Server is running"})
