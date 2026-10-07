"""Main FastAPI application for the catalog service."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from catalog.db import init_db
from catalog.routes import router
from shared.auth import ServiceAuthMiddleware
from shared.observability import RequestCorrelationMiddleware

LIBRARY_NAME = os.getenv("LIBRARY_NAME", "Hanno Memorial Library")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title=f"AI Library - {LIBRARY_NAME} Catalog",
    description="Search and browse the library catalog",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service trust middleware
app.add_middleware(ServiceAuthMiddleware)

# Request correlation (outermost — added last, runs first)
app.add_middleware(RequestCorrelationMiddleware)

# Include routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
