# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p static/uploads static/images static/sfx static/brand_logos

# Set environment variables
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 5000

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Render sätter PORT (ofta 10000) — ingen fast healthcheck-port i Dockerfile
# Run the application (--preload: DB-init i main.py körs bara en gång, inte per worker)
CMD ["sh", "-c", "gunicorn --preload --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120 main:app"]
