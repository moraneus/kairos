# Dockerfile for Kairos - A PBTL Runtime Verification Tool
# This container provides a complete environment for running Kairos monitoring

# Use Python 3.11 slim image for smaller footprint
FROM python:3.11-slim

# Set metadata
LABEL maintainer="Kairos Development Team"
LABEL description="Kairos - A PBTL Runtime Verification Tool for Distributed Systems"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO

# Create a non-root user for security
RUN groupadd -r kairos && useradd -r -g kairos -d /app -s /bin/bash -c "Kairos User" kairos

# Install system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements-dev.txt

# Copy the application code
COPY . .

# Create workspace directory for user files
RUN mkdir -p /workspace /results && \
    chown -R kairos:kairos /app /workspace /results

# Switch to non-root user
USER kairos

# Expose any ports if needed (for future web interface)
# EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import core, parser, utils; print('Kairos components loaded successfully')" || exit 1

# Set default command
CMD ["python", "run_monitor.py", "--help"]

# Build arguments for customization
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

# Add build labels
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="kairos" \
      org.label-schema.description="PBTL Runtime Verification Tool" \
      org.label-schema.url="https://github.com/yourusername/kairos" \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.vcs-url="https://github.com/yourusername/kairos" \
      org.label-schema.vendor="Kairos Development Team" \
      org.label-schema.version=$VERSION \
      org.label-schema.schema-version="1.0"