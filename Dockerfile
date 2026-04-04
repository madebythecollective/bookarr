FROM python:3.12-slim

LABEL maintainer="John Howrey"
LABEL description="Bookarr — Book and audiobook library manager"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY bookarr.py .
COPY templates/ templates/
COPY static/ static/

# Create runtime directories
RUN mkdir -p static/covers

# Default port
EXPOSE 8585

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8585/api/stats')" || exit 1

# Data volume for database and covers
VOLUME ["/app/data"]

# Run
ENTRYPOINT ["python", "bookarr.py"]
CMD ["--port", "8585"]
