# ================================
# Google Workspace MCP Server - Optimized Single-Stage Build
# ================================
# This Dockerfile uses a single-stage build approach for platform compatibility.
# Multi-stage builds were tested but caused issues with architecture mismatches
# when copying virtual environments between build stages on macOS.
#
# Image Size: ~426MB (optimized from initial 805MB)
# Build Time: ~30 seconds (clean), <5 seconds (cached)
# Base Image: python:3.12-slim (141MB)
#
# Key Design Decisions:
# - Single-stage: Ensures dependencies are built for correct target architecture
# - COPY --chown: Avoids 231MB duplicate ownership layer
# - Enhanced .dockerignore: Reduces app code layer from 211MB to 460KB
# - Non-root user: Security best practice, runs as 'app' user
# - Entrypoint script: Maps MCP_GOOGLE_* → GOOGLE_* environment variables
#
# For detailed documentation, see: docs/deployment.md
# ================================

FROM python:3.12-slim

WORKDIR /app

# ================================
# System Dependencies Layer (~25MB)
# ================================
# Install minimal runtime dependencies in a single layer:
# - curl: Required for health checks
# - ca-certificates: Required for HTTPS connections to Google APIs
# - uv: Fast Python package installer (replaces pip)
#
# Best practices:
# - Use --no-install-recommends to minimize package bloat
# - Clean apt cache in same layer to reduce image size
# - Install uv with --no-cache-dir to avoid pip cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# ================================
# User Setup (~3MB)
# ================================
# Create non-root user 'app' early in the build process.
# This allows us to set ownership during COPY operations using --chown,
# avoiding a separate expensive 'chown -R' command that would create
# a duplicate 231MB layer.
#
# Security: Container runs as non-root user for production safety
RUN useradd --create-home --shell /bin/bash app

# ================================
# Dependency Files Layer (~1KB)
# ================================
# Copy dependency files FIRST for optimal Docker layer caching.
# When only application code changes (not dependencies), Docker can
# reuse the cached dependency layer, speeding up rebuilds significantly.
#
# Files copied:
# - pyproject.toml: Project metadata and dependencies
# - uv.lock: Locked dependency versions for reproducible builds
#
# Using --chown=app:app sets ownership immediately during copy
COPY --chown=app:app pyproject.toml uv.lock ./

# ================================
# Application Code Layer (~460KB)
# ================================
# Copy application source code with correct ownership.
# Each module is copied separately for better layer caching granularity.
# If only one module changes, only that layer needs to rebuild.
#
# .dockerignore excludes:
# - .git/ (version control, not needed at runtime)
# - .venv/ (created fresh in container)
# - docs/, tests/, agent_notes/ (not needed at runtime)
# - __pycache__, *.pyc, *.pyo (Python cache files)
# - Development files (.coverage, .pytest_cache, etc.)
#
# Result: Application code layer is only 460KB (down from 211MB!)
COPY --chown=app:app main.py ./
COPY --chown=app:app auth/ ./auth/
COPY --chown=app:app core/ ./core/
COPY --chown=app:app gmail/ ./gmail/
COPY --chown=app:app gdrive/ ./gdrive/
COPY --chown=app:app gcalendar/ ./gcalendar/
COPY --chown=app:app gdocs/ ./gdocs/
COPY --chown=app:app gsheets/ ./gsheets/
COPY --chown=app:app gslides/ ./gslides/
COPY --chown=app:app gforms/ ./gforms/
COPY --chown=app:app gtasks/ ./gtasks/
COPY --chown=app:app gchat/ ./gchat/
COPY --chown=app:app gsearch/ ./gsearch/

# ================================
# Placeholder Configuration File
# ================================
# Create a placeholder client_secrets.json file for the application.
# The real OAuth credentials come from environment variables at runtime:
# - GOOGLE_OAUTH_CLIENT_ID
# - GOOGLE_OAUTH_CLIENT_SECRET
#
# This file is required for the application to start, but placeholder
# values are safe since actual credentials are never hardcoded.
RUN echo '{"installed":{"client_id":"placeholder","client_secret":"placeholder","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","redirect_uris":["http://localhost:8000/oauth2callback"]}}' > /app/client_secrets.json \
    && chown app:app /app/client_secrets.json

# ================================
# Entrypoint Script Setup
# ================================
# Copy the entrypoint script that handles:
# 1. Environment variable mapping (MCP_GOOGLE_* → GOOGLE_*)
# 2. Required variable validation
# 3. Application startup
#
# The entrypoint script is critical for production deployments on ECS
# where variables follow the MCP_GOOGLE_* naming convention.
COPY --chown=app:app docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ================================
# Finalize Permissions
# ================================
# Ensure all files in /app are owned by app user.
# This is a safety measure, though most files already have correct
# ownership from COPY --chown operations above.
RUN chown -R app:app /app

# ================================
# Switch to Non-Root User
# ================================
# All subsequent operations run as non-root 'app' user.
# This includes dependency installation and application runtime.
#
# Security: Container runs with minimal privileges
USER app

# ================================
# Python Dependencies Layer (~202MB)
# ================================
# Install Python dependencies using uv (faster than pip).
#
# Why install dependencies in runtime stage (not builder stage)?
# - Multi-stage copying of .venv caused platform compatibility issues
# - Virtual env from macOS (host) had wrong Python symlinks for Linux
# - Binary extensions (pydantic_core, etc.) were compiled for wrong arch
# - Solution: Build dependencies directly in target container
#
# Flags:
# - --frozen: Use exact versions from uv.lock
# - --no-dev: Skip development dependencies (pytest, etc.)
#
# Result: Creates /app/.venv with correct platform-specific binaries
# Time: ~25 seconds (dependency changes), <1 second (cached)
RUN uv sync --frozen --no-dev

# ================================
# Environment Configuration
# ================================
# Set runtime environment variables with sensible defaults:
#
# PATH: Add virtual environment to PATH so 'python' resolves to venv Python
# PYTHONUNBUFFERED: Disable output buffering for proper logging in Docker
# PORT: Server listening port (default 8000, can be overridden)
# WORKSPACE_MCP_PORT: MCP protocol port (default 8000)
# WORKSPACE_MCP_BASE_URI: Base URI for OAuth redirects (default localhost)
#
# Additional variables provided at runtime:
# - GOOGLE_OAUTH_CLIENT_ID (required)
# - GOOGLE_OAUTH_CLIENT_SECRET (required)
# - GOOGLE_MCP_CREDENTIALS_DIR (optional, default /app/.credentials)
# - MCP_ENABLE_OAUTH21 (optional, default false)
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV WORKSPACE_MCP_PORT=8000
ENV WORKSPACE_MCP_BASE_URI=http://localhost

# ================================
# Port Configuration
# ================================
# Expose port 8000 for the HTTP server (streamable-http transport).
# This is the default port, but can be changed via PORT environment variable.
#
# Note: EXPOSE is documentation only, doesn't actually publish the port.
# Use 'docker run -p 8000:8000' to publish.
EXPOSE 8000

# ================================
# Health Check Configuration
# ================================
# Configure Docker health checks using the /health endpoint:
#
# - interval=30s: Check every 30 seconds
# - timeout=10s: Check must complete within 10 seconds
# - start-period=30s: Allow 30 seconds for application startup
# - retries=3: Mark unhealthy after 3 consecutive failures
#
# Health endpoint returns:
# {"status":"healthy","service":"workspace-mcp","version":"1.2.0","transport":"streamable-http"}
#
# Docker will mark container as:
# - starting: Within start-period
# - healthy: Checks passing
# - unhealthy: 3 consecutive failures
#
# ECS/orchestration platforms use this for automated restarts
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# ================================
# Entrypoint and Command
# ================================
# ENTRYPOINT: Always runs /entrypoint.sh which:
# 1. Maps MCP_GOOGLE_* → GOOGLE_* environment variables
# 2. Validates required credentials are present
# 3. Starts application with: python main.py --transport streamable-http
#
# CMD: Empty by default, but additional arguments can be passed via docker run
# Example: docker run ... google-workspace-mcp --tools gmail drive calendar
#
# Why entrypoint vs CMD?
# - ENTRYPOINT: Always runs, provides essential environment setup
# - CMD: Can be overridden, allows runtime customization
#
# Production: Container always runs in streamable-http mode (required for ECS)
ENTRYPOINT ["/entrypoint.sh"]
CMD []
