FROM python:3.11-slim

# Install system dependencies needed for spatial/GIS libraries
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Copy requirements from your backend subfolder and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy all files from the backend subfolder into the container's /app directory
COPY backend/ .

EXPOSE 8000

# Run Django with Daphne (using config.asgi from your project structure)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]