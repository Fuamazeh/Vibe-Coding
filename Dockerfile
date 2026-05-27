# ============================================================================
# Buea Market Watch — Production Container
# ============================================================================
# Base image: python:3.11-slim keeps the footprint small while providing all
# CPython 3.11 machinery needed by FastAPI, SQLAlchemy, and PyTorch.
# ============================================================================

FROM python:3.11-slim

# ----------------------------------------------------------------------------
# System dependencies
# Installed in a single RUN to keep layer count low; apt cache cleared
# immediately to avoid bloating the image with package index files.
# ----------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------------------------------
# Working directory
# ----------------------------------------------------------------------------
WORKDIR /app

# ----------------------------------------------------------------------------
# Python dependencies
# Copy requirements.txt first to exploit Docker layer caching:
# only re-runs pip install when requirements.txt actually changes.
# ----------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------------------
# Application source
# Copied after dependencies to maximise cache hit rate on code-only changes.
# ----------------------------------------------------------------------------
COPY . .

# ----------------------------------------------------------------------------
# Network exposure
# ----------------------------------------------------------------------------
EXPOSE 8000

# ----------------------------------------------------------------------------
# Runtime command
# Uvicorn ASGI worker; host 0.0.0.0 makes the port reachable outside the
# container; disable --reload in production for stability.
# ----------------------------------------------------------------------------
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
