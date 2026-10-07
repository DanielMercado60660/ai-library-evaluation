FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy workspace files
COPY pyproject.toml ./
COPY shared/ ./shared/
COPY services/catalog/ ./services/catalog/

# Install dependencies
RUN uv sync --package catalog --no-dev

# Copy seed data
COPY data/ ./data/
COPY scripts/ ./scripts/

# Expose port
EXPOSE 8000

# Run the service
CMD ["uv", "run", "--package", "catalog", "uvicorn", "catalog.main:app", "--host", "0.0.0.0", "--port", "8000"]
