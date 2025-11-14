# Task 2.4: Docker Build Test Results

**Date**: 2025-11-12
**Task**: Test Docker Build Locally
**Status**: PARTIALLY SUCCESSFUL - Build works but runtime has issues

## Build Results

### Build Success
- **Result**: Docker build completed successfully ✓
- **Build Time**: ~25 seconds (with layer caching)
- **Errors During Build**: 1 error fixed (user creation order issue)
- **Warnings**: None critical

### Image Size
- **Final Size**: 805MB
- **Expected Size**: ~335MB (from review estimation)
- **Variance**: +470MB (140% larger than expected)

### Layer Breakdown
```
Layer                                   Size
==========================================
Base Debian OS                        101MB
Python 3.12 runtime                    40MB
Runtime dependencies (curl, etc)      14.6MB
Virtual environment (dependencies)    196MB
Application code                      211MB
User creation + ownership             231MB  ⚠️ Unexpectedly large
Other layers                          ~11MB
==========================================
TOTAL                                 805MB
```

## Issues Discovered

### Issue 1: User Creation Order (FIXED)
**Problem**: Dockerfile tried to `chown app:app` before creating the `app` user
**Location**: Line 57 tried to chown before line 60 created user
**Fix Applied**: Moved chown command to same RUN statement as user creation
**Status**: ✅ RESOLVED

```dockerfile
# Before (broken):
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown app:app /entrypoint.sh  # ❌ app user doesn't exist yet
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app

# After (fixed):
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app && chown app:app /entrypoint.sh  # ✅
```

### Issue 2: Virtual Environment Python Symlinks (CRITICAL)
**Problem**: Virtual environment created on macOS has broken symlinks in Docker container
**Root Cause**:
- Builder stage copies venv from host machine (macOS)
- Python symlink points to `/opt/homebrew/opt/python@3.11/bin/python3.11` (macOS Homebrew path)
- This path doesn't exist in Debian container
- workspace-mcp script has shebang: `#!/Users/rob/Projects/busyb/google_workspace_mcp/.venv/bin/python3`

**Evidence**:
```bash
$ docker run --rm --entrypoint /bin/bash google-workspace-mcp:test -c "ls -la /app/.venv/bin/python"
lrwxrwxrwx 1 app app 44 Aug 19 13:01 /app/.venv/bin/python -> /opt/homebrew/opt/python@3.11/bin/python3.11
```

**Impact**: Application cannot start - ModuleNotFoundError
**Status**: ❌ NOT RESOLVED (requires Dockerfile redesign)

### Issue 3: Binary Python Extensions
**Problem**: pydantic_core and other packages with C extensions don't work
**Root Cause**: Extensions compiled for macOS ARM architecture, incompatible with Linux container
**Error**: `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`
**Status**: ❌ NOT RESOLVED (requires Dockerfile redesign)

### Issue 4: Large Image Size
**Problem**: Image is 805MB instead of expected 335MB
**Contributing Factors**:
1. Application code layer: 211MB (includes .git, .venv, and other dev files)
2. User creation layer: 231MB (chown -R on large directory creates duplicate data)
3. Virtual environment: 196MB (reasonable for dependencies)

**Recommendations**:
- Improve .dockerignore to exclude development files (.git, node_modules, *.pyc, etc.)
- Consider multi-stage build optimization
- Use smaller base image alternatives

## Environment Variable Mapping Test

### Result: ✅ SUCCESS
The entrypoint script successfully maps MCP_* environment variables to GOOGLE_* variables:

```
Starting Google Workspace MCP Server...
✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_ID to GOOGLE_OAUTH_CLIENT_ID
✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_SECRET to GOOGLE_OAUTH_CLIENT_SECRET
✓ Mapped MCP_GOOGLE_CREDENTIALS_DIR to GOOGLE_MCP_CREDENTIALS_DIR
Environment variables configured successfully
Starting application...
```

**Test Command**:
```bash
docker run -d \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="test-client-id" \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="test-client-secret" \
  -e MCP_GOOGLE_CREDENTIALS_DIR="s3://test-bucket/credentials/" \
  -e OAUTHLIB_INSECURE_TRANSPORT=1 \
  -p 8000:8000 \
  --name workspace-mcp-test \
  google-workspace-mcp:test
```

## Health Endpoint Test

**Status**: ❌ UNABLE TO TEST
**Reason**: Container cannot start due to Python symlink issues

**Planned Test**:
```bash
curl http://localhost:8000/health
```

## Recommendations for Phase 2.5

### Critical Fixes Required

1. **Redesign Dockerfile to Install Dependencies in Container**
   - Don't copy venv from builder stage
   - Install uv in runtime stage
   - Run `uv sync` in runtime stage to create venv with correct Python paths
   - This ensures platform-specific binaries are built correctly

2. **Improve .dockerignore**
   - Exclude .git directory
   - Exclude .venv directory (we'll create fresh in container)
   - Exclude development files (__pycache__, *.pyc, .pytest_cache, etc.)
   - Exclude documentation and non-essential files

3. **Optimize Layer Sizes**
   - Use `COPY --chown=app:app` instead of separate chown command
   - Consider using `python:3.12-slim-bookworm` base for consistency
   - Combine related RUN commands to reduce layers

### Proposed Dockerfile Changes

```dockerfile
# Runtime stage - Install dependencies fresh in container
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies including uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Create non-root user early
RUN useradd --create-home --shell /bin/bash app

# Copy only necessary files with correct ownership
COPY --chown=app:app pyproject.toml uv.lock ./
COPY --chown=app:app main.py ./
COPY --chown=app:app auth/ ./auth/
COPY --chown=app:app core/ ./core/
COPY --chown=app:app g*/ ./
# ... copy other necessary directories

# Install Python dependencies as app user
USER app
RUN uv sync --frozen --no-dev

# Copy entrypoint script
USER root
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER app

# Set environment and run
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD []
```

## Summary

### What Worked ✅
- Docker build process completes successfully
- Multi-stage build concept is sound
- Entrypoint script environment variable mapping works perfectly
- Error handling in entrypoint script is robust

### What Needs Fixing ❌
- Virtual environment cannot be copied between stages (platform/architecture mismatch)
- Image size is too large (805MB vs 335MB expected)
- Python symlinks break when copying venv from host to container
- Binary extensions (pydantic_core, etc.) are incompatible

### Next Steps
1. Implement new Dockerfile design (install deps in container)
2. Improve .dockerignore to reduce image size
3. Test with proper dependency installation
4. Verify health endpoint and application startup
5. Run full integration test with real OAuth credentials

## Files Modified

1. `/Users/rob/Projects/busyb/google_workspace_mcp/Dockerfile`
   - Fixed user creation order issue

2. `/Users/rob/Projects/busyb/google_workspace_mcp/docker-entrypoint.sh`
   - Changed from `uv run` to `python3` command
   - Added PYTHONPATH for venv site-packages (didn't resolve binary extension issue)

## Build Logs

Full build log saved to: `/tmp/docker_build_log.txt`

Key build metrics:
- Builder stage: ~5.6 seconds
- Runtime stage: ~15 seconds
- Total build time: ~25 seconds (with caching)
- Final image ID: `efd0cdbc2cee`

## Conclusion

The Docker build process works, but the current approach of copying the virtual environment from the builder stage is fundamentally flawed due to platform-specific Python symlinks and binary extensions. The image builds successfully but cannot run the application.

**Recommendation**: Proceed to Task 2.5 with a redesigned Dockerfile that installs dependencies directly in the runtime container rather than copying from the builder stage.
