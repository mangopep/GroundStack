from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="GroundStack API",
    description="Experimental API and GroundStack workspace preview",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return JSONResponse(
        content={
            "status": "ok",
            "message": "Process is responding; dependency readiness is not checked.",
        }
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "RAG Platform API is running. Check /docs for the API documentation."}


app.mount(
    "/workspace",
    StaticFiles(directory=Path(__file__).resolve().parents[2] / "web", html=True),
    name="workspace",
)
