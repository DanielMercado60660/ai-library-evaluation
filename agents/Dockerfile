FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy full workspace (needed for benchmark runner: scripts, tests, services)
COPY pyproject.toml ./
COPY shared/ ./shared/
COPY agents/ ./agents/
COPY services/ ./services/
COPY scripts/ ./scripts/
COPY tests/ ./tests/
COPY data/ ./data/

# Install all workspace packages with dev deps (pytest for benchmark runner)
RUN uv sync --all-packages

# Expose port
EXPOSE 8000

# Run the service
CMD ["uv", "run", "--package", "agents", "uvicorn", "agents.api:app", "--host", "0.0.0.0", "--port", "8000"]
