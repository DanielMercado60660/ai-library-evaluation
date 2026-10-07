"""Main FastAPI application for the registry service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from registry.db import init_db
from registry.routes import router
from shared.auth import ServiceAuthMiddleware
from shared.observability import RequestCorrelationMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="AI Library - Registry Service",
    description="Partner library registry for inter-library loan operations",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
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
    uvicorn.run(app, host="0.0.0.0", port=8004)
