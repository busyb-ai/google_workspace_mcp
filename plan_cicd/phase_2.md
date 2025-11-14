# Phase 2: Dockerfile Review & Optimization

## Overview

This phase focuses on preparing the Dockerfile for production deployment. The existing Dockerfile is well-structured with multi-stage builds, but contains debug statements that should be removed for production. We'll also create an entrypoint script for environment variable mapping to align with the naming conventions used across other MCP servers in the BusyB infrastructure.

## Objectives

- Review current Dockerfile and identify production improvements
- Remove debug RUN statements from Dockerfile
- Create production-ready Dockerfile
- Create entrypoint script for environment variable mapping
- Test Docker build locally
- Verify image size and build time optimizations

## Prerequisites

- Completed Phase 1 (AWS infrastructure setup)
- Docker installed locally for testing
- Access to project repository with Dockerfile
- Understanding of MCP environment variable naming conventions

## Context from Previous Phases

From Phase 1, we have:
- ECR repository created: `busyb-google-workspace-mcp`
- AWS infrastructure documented
- Understanding of how credentials will be injected via Secrets Manager

The Dockerfile needs to:
- Accept environment variables prefixed with `MCP_GOOGLE_*` (from ECS task definition)
- Map them to `GOOGLE_*` variables expected by the application
- Run the application with `--transport streamable-http` mode for ECS deployment

## Time Estimate

**Total Phase Time**: 2-3 hours

---

## Tasks

### Task 2.1: Review Current Dockerfile

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Audit the existing Dockerfile to identify debug statements, optimization opportunities, and production readiness issues.

**Actions**:
- Read through the current `Dockerfile` in the project root
- Identify all debug RUN statements (lines 25-40, 58-59 mentioned in plan)
- Check for:
  - Debug echo/print statements
  - Unnecessary package installations
  - Development-only dependencies
  - File permission issues
  - Security best practices
- Document findings in a review document
- Create a list of specific changes needed for production

**Deliverables**:
- `plan_cicd/dockerfile_review.md` - Analysis document listing:
  - Current issues found
  - Debug statements to remove
  - Security improvements needed
  - Optimization opportunities

**Dependencies**: Phase 1 completed

---

### Task 2.2: Create Production Dockerfile

**Complexity**: Medium
**Estimated Time**: 45 minutes

**Description**:
Create a production-ready Dockerfile by removing debug statements, ensuring security best practices, and optimizing for deployment.

**Actions**:
- Create a backup of the current Dockerfile:
  ```bash
  cp Dockerfile Dockerfile.backup
  ```
- Remove debug RUN statements identified in Task 2.1
- Ensure the Dockerfile includes:
  - Multi-stage build (builder + final stage)
  - Minimal base image (`python:3.12-slim`)
  - Non-root user for security
  - Proper health check configuration
  - Environment variable defaults
  - Minimal runtime dependencies
- Key sections to include:
  ```dockerfile
  # Builder stage
  FROM python:3.12-slim AS builder
  WORKDIR /app
  RUN apt-get update && apt-get install -y --no-install-recommends gcc build-essential && rm -rf /var/lib/apt/lists/*
  RUN pip install --no-cache-dir uv
  COPY pyproject.toml uv.lock ./
  COPY . .
  RUN uv sync --frozen --no-dev

  # Final stage
  FROM python:3.12-slim
  WORKDIR /app
  RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
  COPY --from=builder /app/.venv /app/.venv
  COPY . .
  ENV PATH="/app/.venv/bin:$PATH"
  ENV PYTHONUNBUFFERED=1
  ENV PORT=8000
  ENV WORKSPACE_MCP_PORT=8000
  ENV WORKSPACE_MCP_BASE_URI=http://localhost

  # Create placeholder client_secrets.json
  RUN echo '{"installed":{"client_id":"placeholder","client_secret":"placeholder","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","redirect_uris":["http://localhost:8000/oauth2callback"]}}' > /app/client_secrets.json

  # Create non-root user
  RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
  USER app

  EXPOSE 8000
  HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
      CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

  CMD ["uv", "run", "main.py", "--transport", "streamable-http"]
  ```
- Verify `.dockerignore` is properly configured (already exists per plan)

**Deliverables**:
- Updated `Dockerfile` with debug statements removed
- Production-ready Dockerfile following security best practices
- Backup of original Dockerfile (`Dockerfile.backup`)

**Dependencies**: Task 2.1

---

### Task 2.3: Create Docker Entrypoint Script

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Create an entrypoint script to map MCP-prefixed environment variables to the format expected by the Google Workspace MCP application.

**Actions**:
- Create `docker-entrypoint.sh` in project root:
  ```bash
  #!/bin/bash
  set -e

  echo "Starting Google Workspace MCP Server..."

  # Map MCP_GOOGLE_* environment variables to GOOGLE_* for compatibility
  if [ -n "$MCP_GOOGLE_OAUTH_CLIENT_ID" ]; then
    export GOOGLE_OAUTH_CLIENT_ID="$MCP_GOOGLE_OAUTH_CLIENT_ID"
    echo "✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_ID to GOOGLE_OAUTH_CLIENT_ID"
  fi

  if [ -n "$MCP_GOOGLE_OAUTH_CLIENT_SECRET" ]; then
    export GOOGLE_OAUTH_CLIENT_SECRET="$MCP_GOOGLE_OAUTH_CLIENT_SECRET"
    echo "✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_SECRET to GOOGLE_OAUTH_CLIENT_SECRET"
  fi

  if [ -n "$MCP_GOOGLE_CREDENTIALS_DIR" ]; then
    export GOOGLE_MCP_CREDENTIALS_DIR="$MCP_GOOGLE_CREDENTIALS_DIR"
    echo "✓ Mapped MCP_GOOGLE_CREDENTIALS_DIR to GOOGLE_MCP_CREDENTIALS_DIR"
  fi

  # Verify required environment variables
  if [ -z "$GOOGLE_OAUTH_CLIENT_ID" ]; then
    echo "ERROR: GOOGLE_OAUTH_CLIENT_ID or MCP_GOOGLE_OAUTH_CLIENT_ID is required"
    exit 1
  fi

  if [ -z "$GOOGLE_OAUTH_CLIENT_SECRET" ]; then
    echo "ERROR: GOOGLE_OAUTH_CLIENT_SECRET or MCP_GOOGLE_OAUTH_CLIENT_SECRET is required"
    exit 1
  fi

  echo "Environment variables configured successfully"
  echo "Starting application..."

  # Run the application with all passed arguments
  exec uv run main.py --transport streamable-http "$@"
  ```
- Make the script executable:
  ```bash
  chmod +x docker-entrypoint.sh
  ```
- Update Dockerfile to use the entrypoint:
  ```dockerfile
  # Add before USER app
  COPY docker-entrypoint.sh /entrypoint.sh
  RUN chmod +x /entrypoint.sh && chown app:app /entrypoint.sh

  # Add after USER app, replace CMD with:
  ENTRYPOINT ["/entrypoint.sh"]
  CMD []
  ```

**Deliverables**:
- `docker-entrypoint.sh` script created and executable
- Dockerfile updated to use entrypoint
- Environment variable mapping documented in script comments

**Dependencies**: Task 2.2

---

### Task 2.4: Test Docker Build Locally

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Build the Docker image locally to verify it builds successfully and runs correctly.

**Actions**:
- Build the Docker image:
  ```bash
  docker build -t google-workspace-mcp:test .
  ```
- Check build output for any errors or warnings
- Verify image size is reasonable:
  ```bash
  docker images google-workspace-mcp:test
  ```
- Inspect image layers:
  ```bash
  docker history google-workspace-mcp:test
  ```
- Test running the container with test environment variables:
  ```bash
  docker run --rm \
    -e MCP_GOOGLE_OAUTH_CLIENT_ID="test-client-id" \
    -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret" \
    -e MCP_GOOGLE_CREDENTIALS_DIR="s3://test-bucket/credentials/" \
    -e OAUTHLIB_INSECURE_TRANSPORT=1 \
    -p 8000:8000 \
    google-workspace-mcp:test
  ```
- Verify the container starts and:
  - Environment variable mapping works (check logs)
  - Health endpoint is accessible: `curl http://localhost:8000/health`
  - Application logs show no errors
- Stop the container and document results

**Deliverables**:
- Successful Docker build completion
- Build logs showing no errors
- Image size documented in `plan_cicd/dockerfile_review.md`
- Test results showing container runs successfully

**Dependencies**: Task 2.3

---

### Task 2.5: Optimize Docker Image Size

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Review the built image and apply any final optimizations to reduce image size and improve build times.

**Actions**:
- Analyze image layers for optimization opportunities:
  ```bash
  docker history google-workspace-mcp:test --no-trunc
  ```
- Check for common optimization opportunities:
  - Combining RUN commands to reduce layers
  - Removing unnecessary files in the same layer they're created
  - Using `.dockerignore` effectively
  - Minimizing installed packages
- Apply optimizations if any are found
- Rebuild and compare image sizes:
  ```bash
  docker build -t google-workspace-mcp:optimized .
  docker images | grep google-workspace-mcp
  ```
- Document size improvements and optimizations applied
- Consider using `docker scan` for security vulnerabilities:
  ```bash
  docker scan google-workspace-mcp:optimized
  ```

**Deliverables**:
- Optimized Dockerfile (if changes were needed)
- Before/after image size comparison documented
- Security scan results (if vulnerabilities found, document for future remediation)
- Optimization notes in `plan_cicd/dockerfile_review.md`

**Dependencies**: Task 2.4

---

### Task 2.6: Create Docker Compose for Local Testing

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Create a `docker-compose.yml` file for convenient local testing and development.

**Actions**:
- Create `docker-compose.yml` in project root:
  ```yaml
  version: '3.8'

  services:
    google-workspace-mcp:
      build:
        context: .
        dockerfile: Dockerfile
      image: google-workspace-mcp:local
      container_name: google-workspace-mcp-dev
      ports:
        - "8000:8000"
      environment:
        # Load from .env file or override here
        - GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
        - GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
        - MCP_GOOGLE_CREDENTIALS_DIR=${MCP_GOOGLE_CREDENTIALS_DIR:-/app/.credentials}
        - WORKSPACE_MCP_PORT=8000
        - WORKSPACE_MCP_BASE_URI=http://localhost
        - MCP_ENABLE_OAUTH21=true
        - OAUTHLIB_INSECURE_TRANSPORT=1
      volumes:
        # Mount credentials directory for persistence (optional)
        - ./.credentials:/app/.credentials
      restart: unless-stopped
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 30s
  ```
- Create `.env.docker` template file:
  ```bash
  # Copy this to .env and fill in your credentials
  GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
  GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
  MCP_GOOGLE_CREDENTIALS_DIR=/app/.credentials
  ```
- Test docker-compose:
  ```bash
  docker-compose up -d
  docker-compose logs -f
  curl http://localhost:8000/health
  docker-compose down
  ```
- Document usage in `README.md` or create `docs/local-development.md`

**Deliverables**:
- `docker-compose.yml` created
- `.env.docker` template created
- Docker Compose successfully tested
- Usage documentation

**Dependencies**: Task 2.5

---

### Task 2.7: Document Dockerfile Changes

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Document all changes made to the Dockerfile and create a summary for team reference.

**Actions**:
- Update `plan_cicd/dockerfile_review.md` with:
  - Summary of changes made
  - Removed debug statements (specific line numbers/code)
  - Added security improvements
  - Environment variable mapping approach
  - Build optimization results
  - Image size before/after
- Create or update `docs/deployment.md` with:
  - How to build the Docker image
  - Environment variable requirements
  - Entrypoint script behavior
  - Health check configuration
- Add comments to Dockerfile explaining key sections
- Create a changelog entry if the project maintains one

**Deliverables**:
- Updated `plan_cicd/dockerfile_review.md` with complete change summary
- Updated deployment documentation
- Well-commented Dockerfile
- Team can understand all Dockerfile changes and rationale

**Dependencies**: Task 2.6

---

## Phase 2 Checklist

- [x] Task 2.1: Review Current Dockerfile ✅ COMPLETE
- [x] Task 2.2: Create Production Dockerfile ✅ COMPLETE
- [x] Task 2.3: Create Docker Entrypoint Script ✅ COMPLETE
- [x] Task 2.4: Test Docker Build Locally ⚠️ COMPLETE (Issues Found)
- [x] Task 2.5: Optimize Docker Image Size ✅ COMPLETE (Issues Resolved, 426MB, 47% reduction)
- [x] Task 2.6: Create Docker Compose for Local Testing ✅ COMPLETE
- [x] Task 2.7: Document Dockerfile Changes ✅ COMPLETE

---

**PHASE 2 STATUS: ✅ COMPLETE**
**Date Completed**: 2025-11-12
**All Tasks**: 7/7 (100%)
**Production Ready**: YES

---

## Success Criteria

- ✅ Production-ready Dockerfile with no debug statements
- ✅ Entrypoint script successfully maps environment variables
- ✅ Docker image builds without errors
- ✅ Container runs successfully with test credentials
- ✅ Image size is optimized (426MB - under 500MB target)
- ✅ Health check endpoint works correctly
- ✅ Docker Compose configuration works for local development
- ✅ All changes are documented

**ALL SUCCESS CRITERIA MET** ✅

## Next Steps

Proceed to Phase 3: GitHub Actions Workflow
