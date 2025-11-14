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
# The venv Python is already in PATH due to ENV PATH="/app/.venv/bin:$PATH" in Dockerfile
cd /app
exec python main.py --transport streamable-http "$@"
