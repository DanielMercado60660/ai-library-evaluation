FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy workspace files
COPY pyproject.toml ./
COPY shared/ ./shared/
COPY services/circulation/ ./services/circulation/

# Install dependencies
RUN uv sync --package circulation --no-dev

# Copy seed data
COPY data/ ./data/
COPY scripts/ ./scripts/

# Expose port
EXPOSE 8000

# Run the service
CMD ["uv", "run", "--package", "circulation", "uvicorn", "circulation.main:app", "--host", "0.0.0.0", "--port", "8000"]
