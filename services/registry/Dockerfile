FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy workspace files
COPY pyproject.toml ./
COPY shared/ ./shared/
COPY services/registry/ ./services/registry/

# Install dependencies
RUN uv sync --package registry --no-dev

# Copy scripts
COPY scripts/ ./scripts/

# Expose port
EXPOSE 8000

# Run the service
CMD ["uv", "run", "--package", "registry", "uvicorn", "registry.main:app", "--host", "0.0.0.0", "--port", "8000"]
