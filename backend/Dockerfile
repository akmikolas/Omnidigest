# Stage 1: Builder
# Use an official Python runtime as a parent image
FROM python:3.11-slim as builder

# Set the working directory in the container
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
# libpq-dev and gcc are needed for building some python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
# Make sure we use the virtualenv:
ENV PATH="/opt/venv/bin:$PATH"

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the omnidigest package in editable mode
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir -e .


# Stage 2: Final
# Start from a fresh image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add venv to path
ENV PATH="/opt/venv/bin:$PATH"

# Copy only the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the rest of the application code
COPY src src
COPY src/templates templates

# Expose the port the app runs on
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "omnidigest.main:app", "--host", "0.0.0.0", "--port", "8080"]
