FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for pdf processing and db
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Install gunicorn for production server
RUN pip install gunicorn

# Copy application files
COPY . .

# Environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONPATH=/app
ENV CONFIG_PATH=/app/config.yaml

EXPOSE 5000

# Start Gunicorn (4 workers binding to 0.0.0.0:5000)
CMD ["gunicorn", "-w", "4", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
