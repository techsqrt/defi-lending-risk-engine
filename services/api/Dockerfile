# Build stage
FROM python:3.11-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install poetry==1.7.1

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Export requirements (without dev dependencies)
RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code - mirror repo structure for imports
COPY src/ ./services/api/src/

# Set Python path to repo root equivalent
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run the API
CMD ["uvicorn", "services.api.src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
