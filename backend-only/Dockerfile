FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for compiling Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install build tools and setuptools first
RUN pip install --no-cache-dir setuptools wheel build

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all files
COPY . .

# Install gunicorn for production
RUN pip install gunicorn gevent

# Expose port
EXPOSE 5000

# Run the application with gunicorn for production
CMD ["gunicorn", "--config", "gunicorn_config.py", "app:app"]