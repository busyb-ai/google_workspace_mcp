# Docker Compose Usage Guide

This guide explains how to use Docker Compose for local development and testing of the Google Workspace MCP Server.

## Quick Start

### 1. Configure Environment Variables

Copy the `.env.docker` template to `.env` and fill in your credentials:

```bash
cp .env.docker .env
```

Edit `.env` with your Google OAuth credentials:

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
MCP_GOOGLE_CREDENTIALS_DIR=/app/.credentials
```

### 2. Start the Server

```bash
# Start in detached mode (background)
docker-compose up -d

# Or start with logs visible
docker-compose up
```

### 3. Verify Server is Running

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
    "status": "healthy",
    "service": "workspace-mcp",
    "version": "1.2.0",
    "transport": "streamable-http"
}
```

### 4. View Logs

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View last 50 lines
docker-compose logs --tail=50
```

### 5. Stop the Server

```bash
# Stop containers but keep them
docker-compose stop

# Stop and remove containers
docker-compose down
```

## Features

### Persistent Credentials

The compose configuration mounts `./.credentials` directory for persistent OAuth credentials:

```yaml
volumes:
  - ./.credentials:/app/.credentials
```

This means your authentication persists across container restarts.

### Health Checks

The container includes automatic health checks:

- **Test**: `curl -f http://localhost:8000/health`
- **Interval**: 30 seconds
- **Timeout**: 10 seconds
- **Retries**: 3
- **Start Period**: 30 seconds (grace period on startup)

Check health status:

```bash
docker-compose ps
```

### Auto-Restart

The container automatically restarts if it crashes:

```yaml
restart: unless-stopped
```

This ensures the server stays running unless explicitly stopped.

## Common Commands

### Rebuild Image

If you've made changes to the code:

```bash
# Rebuild and start
docker-compose up --build

# Or rebuild without starting
docker-compose build
```

### Execute Commands in Container

```bash
# Run a command in the running container
docker-compose exec google-workspace-mcp <command>

# Example: Check Python version
docker-compose exec google-workspace-mcp python --version

# Example: List files
docker-compose exec google-workspace-mcp ls -la
```

### View Container Status

```bash
# Check running containers
docker-compose ps

# Check resource usage
docker stats google-workspace-mcp-dev
```

### Environment Variables Override

You can override environment variables on the command line:

```bash
docker-compose up -d \
  -e MCP_ENABLE_OAUTH21=false \
  -e WORKSPACE_MCP_PORT=9000
```

## Configuration

### docker-compose.yml

The compose file includes:

- **Service Name**: `google-workspace-mcp`
- **Container Name**: `google-workspace-mcp-dev`
- **Image Tag**: `google-workspace-mcp:local`
- **Port Mapping**: `8000:8000` (host:container)
- **Network**: Default bridge network

### Environment Variables

Default environment variables set by docker-compose:

| Variable | Default Value | Description |
|----------|--------------|-------------|
| `GOOGLE_OAUTH_CLIENT_ID` | From .env | Google OAuth client ID |
| `GOOGLE_OAUTH_CLIENT_SECRET` | From .env | Google OAuth client secret |
| `MCP_GOOGLE_CREDENTIALS_DIR` | `/app/.credentials` | Credentials storage path |
| `WORKSPACE_MCP_PORT` | `8000` | Server port |
| `WORKSPACE_MCP_BASE_URI` | `http://localhost` | Base URI for OAuth callbacks |
| `MCP_ENABLE_OAUTH21` | `true` | Enable OAuth 2.1 mode |
| `OAUTHLIB_INSECURE_TRANSPORT` | `1` | Allow HTTP for local development |

## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker-compose logs google-workspace-mcp
```

Common issues:
- Missing credentials in `.env`
- Port 8000 already in use
- Docker daemon not running

### Port Already in Use

Change the host port in `docker-compose.yml`:
```yaml
ports:
  - "8080:8000"  # Use port 8080 on host
```

Or stop the conflicting service:
```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### OAuth Not Working

1. Verify credentials are correct in `.env`
2. Check OAuth redirect URI in Google Cloud Console: `http://localhost:8000/oauth2callback`
3. Ensure `OAUTHLIB_INSECURE_TRANSPORT=1` is set for local development

### Credentials Not Persisting

Ensure the volume mount is working:
```bash
# Check if .credentials directory exists
ls -la .credentials

# Check container mount
docker-compose exec google-workspace-mcp ls -la /app/.credentials
```

## Production Deployment

For production use:

1. **Remove insecure transport flag**:
   ```yaml
   environment:
     - OAUTHLIB_INSECURE_TRANSPORT=0
   ```

2. **Use HTTPS**:
   ```yaml
   environment:
     - WORKSPACE_MCP_BASE_URI=https://yourdomain.com
   ```

3. **Add reverse proxy** (nginx, traefik, etc.) for SSL termination

4. **Use secrets management** instead of `.env` file

5. **Configure proper restart policy**:
   ```yaml
   restart: always
   ```

## Next Steps

- See [Configuration Guide](configuration.md) for detailed environment variable documentation
- See [Authentication Guide](authentication.md) for OAuth setup details
- See [Deployment Options](configuration.md#deployment-options) for production deployment
