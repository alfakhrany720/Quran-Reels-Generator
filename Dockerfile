FROM python:3.10-slim

# Prevent Python from creating .pyc files
# and make logs appear immediately
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Prevent interactive apt prompts
ENV DEBIAN_FRONTEND=noninteractive

# ============================================================
# System dependencies
# ============================================================

RUN apt-get update && apt-get install -y \
    ffmpeg \
    imagemagick \
    fonts-dejavu \
    fonts-liberation \
    fontconfig \
    gcc \
    g++ \
    make \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# ImageMagick configuration
# ============================================================

# Allow ImageMagick to work with text/images used by MoviePy
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
        sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/g' /etc/ImageMagick-6/policy.xml || true; \
    fi

# ============================================================
# Application directory
# ============================================================

WORKDIR /app

# ============================================================
# Install Python dependencies first
# This improves Docker build caching
# ============================================================

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================
# Copy application files
# ============================================================

COPY . /app

# ============================================================
# Make sure required directories exist
# ============================================================

RUN mkdir -p \
    /app/outputs \
    /app/outputs/audio \
    /app/outputs/video \
    /app/fonts

# ============================================================
# Font cache
# ============================================================

RUN fc-cache -f -v || true

# ============================================================
# Environment variables
# ============================================================

ENV FFMPEG_BINARY=/usr/bin/ffmpeg
ENV IMAGEIO_FFMPEG_EXE=/usr/bin/ffmpeg
ENV IMAGEMAGICK_BINARY=/usr/bin/convert

# ============================================================
# Flask / Coolify
# ============================================================

EXPOSE 5000

# ============================================================
# Start application
# ============================================================

CMD ["python", "main.py"]
