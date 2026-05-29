# Stage 1: Builder
# Use an official Python runtime as a parent image
FROM python:3.11-slim as builder

# Proxy support — pass with: docker build --build-arg HTTP_PROXY=http://host:10809 ...
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ARG NO_PROXY
ARG no_proxy

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
# Set PYTHONPATH so 'omnidigest' module can be imported from 'src' directory
ENV PYTHONPATH="/app:$PYTHONPATH"

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install the omnidigest package (non-editable mode)
COPY pyproject.toml .
COPY src src
RUN pip install --no-cache-dir .


# Stage 2: Final
# Start from a fresh image
FROM python:3.11-slim

# Proxy support
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG http_proxy
ARG https_proxy
ARG NO_PROXY
ARG no_proxy

# Install system dependencies for healthcheck and entrypoint
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Add venv to path
ENV PATH="/opt/venv/bin:$PATH"
# Set PYTHONPATH so 'omnidigest' module can be imported from 'src' directory
ENV PYTHONPATH="/app:$PYTHONPATH"

# Copy only the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the rest of the application code
COPY src src
COPY src/templates templates
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Create data directory for bootstrap artifacts and non-root user
RUN mkdir -p /data && chmod 755 /docker-entrypoint.sh && \
    addgroup --system appgroup && \
    adduser --system --no-create-home --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app /data

# Switch to non-root user
USER appuser:appgroup

# Expose the port the app runs on
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:8080/api/health || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
