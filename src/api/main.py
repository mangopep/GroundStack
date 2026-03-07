from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(
    title="RAG Platform API",
    description="API for the Retrieval-Augmented Generation Platform",
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "healthy",
            "message": "Welcome to the RAG Platform API. The endpoints will be built in Week 2!"
        }
    )

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Platform API is running. Check /docs for the API documentation."}
