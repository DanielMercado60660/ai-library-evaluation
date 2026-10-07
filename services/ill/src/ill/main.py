"""FastAPI application for the Inter-Library Loan (ILL) service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ill.db import init_db
from ill.routes import router
from shared.auth import ServiceAuthMiddleware
from shared.observability import RequestCorrelationMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup and shutdown.

    Startup:
    - Initialize database tables
    - Any other startup tasks

    Shutdown:
    - Cleanup resources if needed
    """
    # Startup
    init_db()
    yield
    # Shutdown
    # Add cleanup here if needed


# Create FastAPI application
app = FastAPI(
    title="AI Library - ILL Service",
    description="Inter-Library Loan service for the Pachyderm Library Network",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service trust middleware
app.add_middleware(ServiceAuthMiddleware)

# Request correlation (outermost — added last, runs first)
app.add_middleware(RequestCorrelationMiddleware)

# Include API routes
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "ill.main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
    )
