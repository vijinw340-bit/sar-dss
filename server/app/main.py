"""FastAPI application entry point for SAR-DSS."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.api import api_router
from app.core.config import settings
from app.core.database import init_db

app = FastAPI(
    title="SAR-DSS - Search and Rescue Decision Support System",
    description=(
        "Backend API for calculating and plotting the probable search area of a "
        "missing aircraft from its Last Known Position (LKP). Developed for the "
        "Airports Authority of India."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
)

# CORS - restrict to configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create tables on startup (production DB migrations via Alembic optional)."""
    init_db()


@app.get("/api/v1/health", tags=["System"])
def health() -> JSONResponse:
    """Health check endpoint used by load balancers and Docker healthchecks."""
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.APP_NAME,
            "environment": settings.APP_ENV,
        }
    )


app.include_router(api_router)
