# Docker Deployment Guide

This guide covers deploying the Google Workspace MCP Server using Docker.

## Table of Contents

- [Building the Docker Image](#building-the-docker-image)
- [Environment Variables](#environment-variables)
- [Running the Container](#running-the-container)
- [Entrypoint Script Behavior](#entrypoint-script-behavior)
- [Health Check Configuration](#health-check-configuration)
- [Docker Compose](#docker-compose)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Building the Docker Image

### Basic Build

Build the Docker image from the project root:

```bash
docker build -t google-workspace-mcp:latest .
```

### Build with Tags

For production deployments, tag with version numbers:

```bash
docker build -t google-workspace-mcp:1.2.0 -t google-workspace-mcp:latest .
```

### Build Time

- **First build** (no cache): ~30 seconds
- **Cached builds** (no changes): <5 seconds
- **Code changes only**: ~5-10 seconds
- **Dependency changes**: ~25 seconds

### Build Context

The `.dockerignore` file excludes unnecessary files from the build context:
- `.git/` - Version control
- `.venv/` - Virtual environments
- `docs/`, `agent_notes/`, `plan_cicd/` - Documentation
- `tests/` - Test files
- `__pycache__/`, `*.pyc`, `*.pyo` - Python cache
- IDE and OS files

**Result**: Application code layer is only ~460KB

## Environment Variables

### Required Variables

The following environment variables **must** be provided:

#### Option 1: Using MCP_GOOGLE_* Prefix (Recommended for ECS)

```bash
MCP_GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
MCP_GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

These are automatically mapped to `GOOGLE_*` variables by the entrypoint script.

#### Option 2: Using GOOGLE_* Prefix (Direct)

```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

### Optional Variables

#### Credential Storage Location

```bash
# Local file storage (default)
GOOGLE_MCP_CREDENTIALS_DIR=/app/.credentials

# AWS S3 storage
MCP_GOOGLE_CREDENTIALS_DIR=s3://your-bucket/credentials/
```

#### OAuth Development Mode

```bash
# Allow OAuth over HTTP (development only - NEVER in production)
OAUTHLIB_INSECURE_TRANSPORT=1
```

#### Server Configuration

These have defaults but can be overridden:

```bash
PORT=8000                              # Server port (default: 8000)
WORKSPACE_MCP_PORT=8000                # MCP server port (default: 8000)
WORKSPACE_MCP_BASE_URI=http://localhost # Base URI (default: http://localhost)
```

#### Single-User Mode

```bash
USER_GOOGLE_EMAIL=your-email@gmail.com  # Pre-configure user email
MCP_SINGLE_USER_MODE=1                  # Skip session validation
```

#### OAuth 2.1 Configuration

```bash
MCP_ENABLE_OAUTH21=true                 # Enable OAuth 2.1 mode
```

### Environment Variable Summary

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MCP_GOOGLE_OAUTH_CLIENT_ID` or `GOOGLE_OAUTH_CLIENT_ID` | ✅ Yes | None | Google OAuth client ID |
| `MCP_GOOGLE_OAUTH_CLIENT_SECRET` or `GOOGLE_OAUTH_CLIENT_SECRET` | ✅ Yes | None | Google OAuth client secret |
| `MCP_GOOGLE_CREDENTIALS_DIR` or `GOOGLE_MCP_CREDENTIALS_DIR` | No | `/app/.credentials` | Credential storage location |
| `PORT` | No | `8000` | Server listening port |
| `WORKSPACE_MCP_PORT` | No | `8000` | MCP server port |
| `WORKSPACE_MCP_BASE_URI` | No | `http://localhost` | Server base URI |
| `OAUTHLIB_INSECURE_TRANSPORT` | No | Not set | Allow HTTP OAuth (dev only) |
| `USER_GOOGLE_EMAIL` | No | None | Default user email |
| `MCP_SINGLE_USER_MODE` | No | `0` | Single-user mode |
| `MCP_ENABLE_OAUTH21` | No | `false` | Enable OAuth 2.1 |

## Running the Container

### Basic Run (Development)

```bash
docker run -d \
  -p 8000:8000 \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  -e OAUTHLIB_INSECURE_TRANSPORT=1 \
  --name google-workspace-mcp \
  google-workspace-mcp:latest
```

### Run with Environment File

Create a `.env` file:

```bash
# .env
MCP_GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
MCP_GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
OAUTHLIB_INSECURE_TRANSPORT=1
```

Run with the file:

```bash
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name google-workspace-mcp \
  google-workspace-mcp:latest
```

### Run with Persistent Credentials (Volume Mount)

```bash
docker run -d \
  -p 8000:8000 \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  -v $(pwd)/.credentials:/app/.credentials \
  --name google-workspace-mcp \
  google-workspace-mcp:latest
```

**Benefits**:
- Credentials persist across container restarts
- No need to reauthenticate after redeployment

### Run with S3 Credential Storage

```bash
docker run -d \
  -p 8000:8000 \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  -e MCP_GOOGLE_CREDENTIALS_DIR="s3://your-bucket/credentials/" \
  -e AWS_ACCESS_KEY_ID="your-aws-key" \
  -e AWS_SECRET_ACCESS_KEY="your-aws-secret" \
  -e AWS_REGION="us-east-1" \
  --name google-workspace-mcp \
  google-workspace-mcp:latest
```

Or on AWS ECS with IAM role (no AWS credentials needed):

```bash
docker run -d \
  -p 8000:8000 \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  -e MCP_GOOGLE_CREDENTIALS_DIR="s3://your-bucket/credentials/" \
  --name google-workspace-mcp \
  google-workspace-mcp:latest
```

### Common Run Options

```bash
docker run -d \                          # Run in detached mode
  -p 8000:8000 \                         # Port mapping (host:container)
  -e VAR=value \                         # Set environment variable
  --env-file .env \                      # Load variables from file
  -v /host/path:/container/path \        # Volume mount
  --name container-name \                # Container name
  --restart unless-stopped \             # Restart policy
  --health-cmd="curl -f http://localhost:8000/health || exit 1" \  # Health check
  --health-interval=30s \                # Health check interval
  google-workspace-mcp:latest            # Image to run
```

## Entrypoint Script Behavior

The `docker-entrypoint.sh` script performs the following actions when the container starts:

### 1. Environment Variable Mapping

Maps MCP infrastructure naming to application naming:

```bash
MCP_GOOGLE_OAUTH_CLIENT_ID       → GOOGLE_OAUTH_CLIENT_ID
MCP_GOOGLE_OAUTH_CLIENT_SECRET   → GOOGLE_OAUTH_CLIENT_SECRET
MCP_GOOGLE_CREDENTIALS_DIR       → GOOGLE_MCP_CREDENTIALS_DIR
```

**Logging**:
```
Starting Google Workspace MCP Server...
✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_ID to GOOGLE_OAUTH_CLIENT_ID
✓ Mapped MCP_GOOGLE_OAUTH_CLIENT_SECRET to GOOGLE_OAUTH_CLIENT_SECRET
✓ Mapped MCP_GOOGLE_CREDENTIALS_DIR to GOOGLE_MCP_CREDENTIALS_DIR
```

### 2. Variable Validation

Verifies required environment variables are set:

```bash
# Required variables
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
```

**Success**:
```
Environment variables configured successfully
Starting application...
```

**Failure** (missing variable):
```
ERROR: GOOGLE_OAUTH_CLIENT_ID or MCP_GOOGLE_OAUTH_CLIENT_ID is required
[Container exits with code 1]
```

### 3. Application Launch

Starts the application with fixed configuration:

```bash
cd /app
exec python main.py --transport streamable-http "$@"
```

**Notes**:
- Always runs in `streamable-http` mode (required for Docker/ECS)
- Uses `exec` to replace shell process (proper signal handling)
- Passes through any additional arguments from `docker run` command
- Python from virtual environment (already in PATH)

### Entrypoint Script Location

- **In Image**: `/entrypoint.sh`
- **Source**: `/Users/rob/Projects/busyb/google_workspace_mcp/docker-entrypoint.sh`
- **Permissions**: Executable (`chmod +x`)
- **Owner**: `app:app`

### Overriding the Entrypoint

If needed, you can override the entrypoint:

```bash
# Run bash instead of application
docker run -it --entrypoint bash google-workspace-mcp:latest

# Run with custom arguments
docker run -d \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="..." \
  -e MCP_GOOGLE_OAUTH_CLIENT_SECRET="..." \
  google-workspace-mcp:latest --tools gmail drive calendar
```

## Health Check Configuration

### Default Health Check

The Dockerfile includes a health check that runs automatically:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

### Health Check Parameters

- **Interval**: 30 seconds (time between checks)
- **Timeout**: 10 seconds (max time for check to complete)
- **Start Period**: 30 seconds (initialization time, failures don't count)
- **Retries**: 3 (consecutive failures before marking unhealthy)

### Health Endpoint

The server exposes a health endpoint:

**URL**: `http://localhost:8000/health`

**Response** (healthy):
```json
{
  "status": "healthy",
  "service": "workspace-mcp",
  "version": "1.2.0",
  "transport": "streamable-http"
}
```

**HTTP Status**: `200 OK`

### Checking Health Manually

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check Docker health status
docker ps

# View detailed health info
docker inspect --format='{{json .State.Health}}' google-workspace-mcp

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' google-workspace-mcp
```

### Container Health States

- **starting**: Container is starting (within start-period)
- **healthy**: Health checks passing
- **unhealthy**: 3 consecutive health checks failed

### Disable Health Check

If needed, disable the health check:

```bash
docker run -d \
  --no-healthcheck \
  -e MCP_GOOGLE_OAUTH_CLIENT_ID="..." \
  google-workspace-mcp:latest
```

## Docker Compose

For local development, use Docker Compose for easier management.

### Basic docker-compose.yml

```yaml
version: '3.8'

services:
  google-workspace-mcp:
    build: .
    container_name: google-workspace-mcp-dev
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
      - GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
      - OAUTHLIB_INSECURE_TRANSPORT=1
    volumes:
      - ./.credentials:/app/.credentials
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### Quick Start with Docker Compose

```bash
# Start server (builds image if needed)
docker-compose up -d

# View logs
docker-compose logs -f

# Check status
docker-compose ps

# Stop server
docker-compose down

# Rebuild and start (after code changes)
docker-compose up --build -d
```

See [docker-compose-usage.md](./docker-compose-usage.md) for detailed Docker Compose documentation.

## Production Deployment

### AWS ECS/Fargate

For production deployment on AWS ECS:

1. **Push Image to ECR**:
   ```bash
   # Authenticate to ECR
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

   # Tag image
   docker tag google-workspace-mcp:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest

   # Push image
   docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest
   ```

2. **ECS Task Definition** (example):
   ```json
   {
     "family": "google-workspace-mcp",
     "containerDefinitions": [
       {
         "name": "workspace-mcp",
         "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest",
         "essential": true,
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "MCP_GOOGLE_CREDENTIALS_DIR",
             "value": "s3://busyb-credentials/google-workspace-mcp/"
           },
           {
             "name": "MCP_ENABLE_OAUTH21",
             "value": "true"
           }
         ],
         "secrets": [
           {
             "name": "MCP_GOOGLE_OAUTH_CLIENT_ID",
             "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:google-workspace-mcp/oauth-client-id"
           },
           {
             "name": "MCP_GOOGLE_OAUTH_CLIENT_SECRET",
             "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:google-workspace-mcp/oauth-client-secret"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/google-workspace-mcp",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         },
         "healthCheck": {
           "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
           "interval": 30,
           "timeout": 10,
           "retries": 3,
           "startPeriod": 30
         }
       }
     ],
     "taskRoleArn": "arn:aws:iam::123456789012:role/GoogleWorkspaceMCPTaskRole",
     "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "256",
     "memory": "512"
   }
   ```

3. **IAM Task Role** (for S3 access):
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:GetObject",
           "s3:PutObject",
           "s3:DeleteObject"
         ],
         "Resource": "arn:aws:s3:::busyb-credentials/google-workspace-mcp/*"
       },
       {
         "Effect": "Allow",
         "Action": "s3:ListBucket",
         "Resource": "arn:aws:s3:::busyb-credentials"
       }
     ]
   }
   ```

### Production Environment Variables

For production, always use:

```bash
# Required
MCP_GOOGLE_OAUTH_CLIENT_ID=...
MCP_GOOGLE_OAUTH_CLIENT_SECRET=...

# Use S3 for credentials
MCP_GOOGLE_CREDENTIALS_DIR=s3://your-bucket/credentials/

# Enable OAuth 2.1
MCP_ENABLE_OAUTH21=true

# IMPORTANT: Never set OAUTHLIB_INSECURE_TRANSPORT in production
# HTTPS is required for OAuth in production
```

### Security Best Practices

1. **Never expose OAuth credentials in logs**:
   - Use AWS Secrets Manager for sensitive variables
   - Environment variables are logged in ECS task definitions

2. **Use HTTPS for OAuth**:
   - Production deployments must use HTTPS
   - Configure ALB/NLB with SSL certificate
   - Remove `OAUTHLIB_INSECURE_TRANSPORT` variable

3. **Use S3 for credential storage**:
   - Enables multi-instance deployments
   - Centralized credential management
   - Automatic encryption at rest

4. **Run as non-root user**:
   - Container already configured to run as `app` user
   - No changes needed

5. **Monitor health checks**:
   - Configure CloudWatch alarms for unhealthy tasks
   - Auto-restart unhealthy containers

## Troubleshooting

### Container Won't Start

**Symptom**: Container exits immediately

**Check**:
```bash
# View container logs
docker logs google-workspace-mcp

# Check exit code
docker inspect google-workspace-mcp --format='{{.State.ExitCode}}'
```

**Common Causes**:
- Missing required environment variables (exit code 1)
- Invalid OAuth credentials
- Port already in use

**Solution**:
```bash
# Verify environment variables
docker exec google-workspace-mcp env | grep GOOGLE

# Check if port is available
lsof -i :8000
```

### Health Check Failing

**Symptom**: Container marked as unhealthy

**Check**:
```bash
# Test health endpoint manually
docker exec google-workspace-mcp curl -f http://localhost:8000/health

# View health check logs
docker inspect --format='{{range .State.Health.Log}}{{.Output}}{{end}}' google-workspace-mcp
```

**Common Causes**:
- Application not fully started (within start-period is OK)
- Port misconfiguration
- Application crashed

**Solution**:
```bash
# View application logs
docker logs google-workspace-mcp

# Check if application is listening
docker exec google-workspace-mcp netstat -tlnp | grep 8000
```

### "No such file or directory" Errors

**Symptom**: Application can't find files

**Possible Cause**: Running in wrong directory

**Solution**: Entrypoint script includes `cd /app` before running application

### Permission Denied Errors

**Symptom**: Can't write credentials or logs

**Check**:
```bash
# Verify user
docker exec google-workspace-mcp whoami
# Should output: app

# Check file permissions
docker exec google-workspace-mcp ls -la /app
```

**Solution**: All files should be owned by `app:app` (handled by Dockerfile)

### Image Size Issues

**Check**:
```bash
# View image size
docker images google-workspace-mcp

# View layer sizes
docker history google-workspace-mcp:latest
```

**Expected Size**: ~426MB

If larger:
- Check if .dockerignore is working
- Rebuild with `--no-cache` to ensure clean build
- Verify no unnecessary files in build context

### Environment Variable Mapping Not Working

**Symptom**: Application can't find OAuth credentials

**Check**:
```bash
# View mapped variables
docker logs google-workspace-mcp | grep "Mapped"

# Check inside container
docker exec google-workspace-mcp env | grep GOOGLE
```

**Solution**: Ensure using correct variable names:
- `MCP_GOOGLE_OAUTH_CLIENT_ID` (mapped by entrypoint)
- OR `GOOGLE_OAUTH_CLIENT_ID` (used directly)

### S3 Credential Storage Issues

**Symptom**: Can't read/write credentials to S3

**Check**:
```bash
# Verify AWS credentials
docker exec google-workspace-mcp env | grep AWS

# Test S3 access
docker exec google-workspace-mcp aws s3 ls s3://your-bucket/
```

**Common Causes**:
- Missing AWS credentials
- Incorrect IAM permissions
- Bucket doesn't exist
- Wrong region

**Solution**: See [authentication.md - S3 Storage Troubleshooting](./authentication.md#s3-storage-issues)

### Container Logs

For debugging, increase log verbosity:

```bash
# View all logs
docker logs google-workspace-mcp

# Follow logs in real-time
docker logs -f google-workspace-mcp

# Last 100 lines
docker logs --tail 100 google-workspace-mcp

# Logs since timestamp
docker logs --since 2025-11-12T10:00:00 google-workspace-mcp
```

---

## AWS ECS/Fargate Production Deployment

This section covers deploying the Google Workspace MCP Server on AWS ECS with Fargate, including the complete production setup with ALB, service discovery, and monitoring.

### Overview

The production deployment uses:
- **AWS ECS with Fargate**: Serverless container orchestration
- **Application Load Balancer (ALB)**: External HTTPS access with SSL termination
- **AWS Cloud Map**: Service discovery for internal communication
- **AWS Secrets Manager**: Secure credential storage
- **Amazon S3**: OAuth token persistence across container restarts
- **CloudWatch Logs**: Centralized logging with 30-day retention

### Architecture

```
Internet → ALB (HTTPS) → ECS Service (Private Subnets) → Container (Port 8000)
                          ↓
                    Cloud Map Service Discovery
                          ↓
                    Core Agent (Internal Communication)
```

### ECS Task Definition Configuration

#### Task Definition Overview

- **Task Definition ARN**: `arn:aws:ecs:us-east-1:758888582357:task-definition/busyb-google-workspace-mcp:3`
- **Family**: `busyb-google-workspace-mcp`
- **Launch Type**: FARGATE
- **Network Mode**: awsvpc (required for Fargate)
- **CPU**: 512 (0.5 vCPU)
- **Memory**: 1024 MB (1 GB)
- **Platform Version**: LATEST

#### IAM Roles

**Task Execution Role** (used by ECS to start the task):
- **Role ARN**: `arn:aws:iam::758888582357:role/ecsTaskExecutionRole`
- **Permissions**:
  - Pull Docker images from ECR
  - Retrieve secrets from AWS Secrets Manager
  - Write logs to CloudWatch Logs

**Task Role** (used by the running container):
- **Role ARN**: `arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role`
- **Permissions**:
  - Read/write/delete objects in S3 bucket (OAuth tokens)
  - List S3 bucket contents
  - Read secrets from AWS Secrets Manager

#### Container Configuration

**Container Name**: `busyb-google-workspace-mcp`

**Image**: `758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest`

**Port Mappings**:
- Container Port: 8000 (TCP)
- Protocol: tcp

**Environment Variables**:
```json
{
  "PORT": "8000",
  "WORKSPACE_MCP_PORT": "8000",
  "WORKSPACE_MCP_BASE_URI": "http://google-workspace.busyb.local",
  "MCP_ENABLE_OAUTH21": "true",
  "MCP_SINGLE_USER_MODE": "0",
  "OAUTHLIB_INSECURE_TRANSPORT": "0"
}
```

**Secrets** (from AWS Secrets Manager):
```json
{
  "GOOGLE_OAUTH_CLIENT_ID": {
    "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx:GOOGLE_OAUTH_CLIENT_ID::"
  },
  "GOOGLE_OAUTH_CLIENT_SECRET": {
    "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z:GOOGLE_OAUTH_CLIENT_SECRET::"
  },
  "GOOGLE_MCP_CREDENTIALS_DIR": {
    "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM"
  }
}
```

**Note**: The OAuth credentials are stored as JSON objects in Secrets Manager, so the secret ARN includes the JSON key name (`:GOOGLE_OAUTH_CLIENT_ID::`). The S3 bucket path is stored as a plain string value.

#### Health Check Configuration

**Container Health Check**:
- **Command**: `curl -f http://localhost:8000/health || exit 1`
- **Interval**: 30 seconds
- **Timeout**: 5 seconds
- **Retries**: 3 consecutive failures before marking unhealthy
- **Start Period**: 60 seconds (grace period for application startup)

**Health Check Behavior**:
- During the start period (first 60 seconds), failures don't count toward the retry limit
- After start period, 3 consecutive failures will mark the container as unhealthy
- ECS will automatically replace unhealthy tasks

#### Logging Configuration

**Log Driver**: awslogs (CloudWatch Logs)

**Log Configuration**:
```json
{
  "awslogs-group": "/ecs/busyb-google-workspace-mcp",
  "awslogs-region": "us-east-1",
  "awslogs-stream-prefix": "ecs",
  "awslogs-create-group": "true"
}
```

**Log Retention**: 30 days

**Log Group ARN**: `arn:aws:logs:us-east-1:758888582357:log-group:/ecs/busyb-google-workspace-mcp:*`

**Viewing Logs**:
```bash
# Tail logs in real-time
aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1

# View logs from specific time
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --region us-east-1

# Filter logs by pattern
aws logs tail /ecs/busyb-google-workspace-mcp --follow --filter-pattern "ERROR" --region us-east-1
```

### ECS Service Configuration

#### Service Overview

- **Service Name**: `busyb-google-workspace-mcp-service`
- **Service ARN**: `arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-google-workspace-mcp-service`
- **Cluster**: `busyb-cluster`
- **Task Definition**: `busyb-google-workspace-mcp:3` (revision 3)
- **Launch Type**: FARGATE
- **Platform Version**: LATEST
- **Desired Count**: 1 task
- **Status**: ACTIVE

#### Deployment Configuration

**Deployment Strategy**:
- **Maximum Percent**: 200 (allows 2 tasks during deployment)
- **Minimum Healthy Percent**: 100 (ensures at least 1 task is always running)

**Deployment Behavior**:
1. New task is started first (with new code/image)
2. New task must pass health checks
3. Once new task is healthy, old task is stopped
4. Zero-downtime deployments

**Rollback**:
- ECS automatically rolls back failed deployments
- If new task fails health checks, ECS stops deployment and keeps old task running

#### Health Check Grace Period

- **Grace Period**: 60 seconds
- Allows the application to start up before ALB health checks count toward target health
- Prevents premature task replacement during startup

### Networking Setup

#### VPC Configuration

- **VPC ID**: `vpc-0111b7630bcb61b61`
- **CIDR Block**: 10.0.0.0/16
- **DNS Resolution**: Enabled (required for service discovery)

#### Subnet Configuration

**Private Subnets** (where ECS tasks run):
- **Subnet 1**: `subnet-0d2d334cbe1467f4b` (us-east-1a, 10.0.10.0/24)
- **Subnet 2**: `subnet-0ae07f54c7454fe72` (us-east-1b, 10.0.11.0/24)

**Multi-AZ Deployment**:
- Tasks are distributed across multiple availability zones
- Provides high availability and fault tolerance
- If one AZ fails, tasks in other AZ continue to serve traffic

**Public IP Assignment**: DISABLED
- Tasks run in private subnets with no direct internet access
- Outbound internet access through NAT Gateway
- Enhanced security posture

#### Security Groups

**ECS Security Group** (`sg-0ebf38ea0618aef2d` - busyb-ecs-sg):

**Inbound Rules**:
- **Port 8000-8080 (TCP)** from ALB security group (`sg-0b5d6bf9cab3a6a83`)
  - Allows ALB to forward traffic to containers
- **All traffic** from same security group (self-referencing)
  - Allows inter-service communication via service discovery

**Outbound Rules**:
- **All traffic** to 0.0.0.0/0
  - Required for:
    - Pulling Docker images from ECR
    - Accessing AWS Secrets Manager
    - Accessing S3 for OAuth tokens
    - Making Google API calls
    - DNS resolution

### Service Discovery Setup

#### AWS Cloud Map Configuration

**Service Discovery Details**:
- **Service Name**: `google-workspace`
- **Service ID**: `srv-gxethbb34gto3cbr`
- **Service ARN**: `arn:aws:servicediscovery:us-east-1:758888582357:service/srv-gxethbb34gto3cbr`
- **Namespace**: `busyb.local`
- **Namespace ID**: `ns-vt3hun37drrxdy7p`
- **DNS Name**: `google-workspace.busyb.local`

**DNS Configuration**:
- **Type A Record**: Points to task IP addresses (TTL: 60 seconds)
- **Type SRV Record**: Includes port information (TTL: 60 seconds)
- **Routing Policy**: MULTIVALUE (returns all healthy targets)

**Health Check**:
- **Type**: Custom health check
- **Failure Threshold**: 1 (immediate failover)
- **Integrated with ECS task health status**

#### Internal Access via Service Discovery

From any service in the same VPC (e.g., Core Agent):

```bash
# Health check
curl http://google-workspace.busyb.local:8000/health

# MCP endpoint (used by Core Agent)
curl http://google-workspace.busyb.local:8000/mcp/

# OAuth authorization
curl http://google-workspace.busyb.local:8000/oauth2/authorize
```

**Advantages**:
- No path prefix issues (unlike ALB routing)
- Direct container-to-container communication
- Automatic service discovery and load balancing
- Low latency (no ALB overhead)

### ALB Integration

#### Application Load Balancer

- **ALB Name**: `busyb-alb`
- **ALB ARN**: `arn:aws:elasticloadbalancing:us-east-1:758888582357:loadbalancer/app/busyb-alb/5111c2db275a2af3`
- **DNS Name**: `busyb-alb-1791678277.us-east-1.elb.amazonaws.com`
- **Scheme**: internet-facing
- **SSL Certificate**: `busyb.ai` (*.busyb.ai)

#### Target Group

**Target Group Details**:
- **Name**: `busyb-google-workspace`
- **ARN**: `arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e`
- **Target Type**: IP (required for Fargate)
- **Protocol**: HTTP
- **Port**: 8000
- **VPC**: `vpc-0111b7630bcb61b61`

**Health Check Configuration**:
- **Health Check Path**: `/health`
- **Health Check Protocol**: HTTP
- **Health Check Port**: traffic-port (8000)
- **Health Check Interval**: 30 seconds
- **Health Check Timeout**: 5 seconds
- **Healthy Threshold**: 2 consecutive successes
- **Unhealthy Threshold**: 3 consecutive failures
- **Success Codes**: 200

**Target Registration**:
- ECS automatically registers task IP addresses with the target group
- When tasks start, they are added to the target group
- When tasks stop, they are deregistered from the target group

#### Listener Rule

**HTTPS Listener (Port 443)**:
- **Listener ARN**: `arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23`
- **SSL Certificate**: arn:aws:acm:us-east-1:758888582357:certificate/f0d9ff36-0ab5-4348-bcac-7f5aef60da05

**Routing Rule** (Priority 50):
- **Rule ARN**: `arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4`
- **Priority**: 50
- **Path Pattern**: `/google-workspace/*`
- **Action**: Forward to `busyb-google-workspace` target group

**Known Issue - Path Prefix**:
⚠️ The application does not currently handle the `/google-workspace/` path prefix. Requests through the ALB with this prefix will return 404. For details and resolution options, see the [Operations Guide](./operations.md#troubleshooting-path-prefix-issue).

**HTTP Listener (Port 80)**:
- Automatically redirects all HTTP traffic to HTTPS (301 redirect)

#### External Access URLs

**Via ALB DNS** (without custom domain):
```bash
# Health check (bypasses path prefix via target group health check)
curl -k https://busyb-alb-1791678277.us-east-1.elb.amazonaws.com/health

# Note: The following URLs have path prefix issues
# curl -k https://busyb-alb-1791678277.us-east-1.elb.amazonaws.com/google-workspace/health
```

**Via Custom Domain** (when DNS is configured):
```bash
# If google-workspace.busyb.ai is pointed to the ALB
curl https://google-workspace.busyb.ai/health
```

### Deployment Process

#### Initial Deployment (Manual)

1. **Register Task Definition**:
   ```bash
   aws ecs register-task-definition \
     --cli-input-json file://ecs/task-definition-google-workspace-mcp.json \
     --region us-east-1
   ```

2. **Create ECS Service**:
   ```bash
   aws ecs create-service \
     --cluster busyb-cluster \
     --service-name busyb-google-workspace-mcp-service \
     --task-definition busyb-google-workspace-mcp \
     --desired-count 1 \
     --launch-type FARGATE \
     --platform-version LATEST \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-0ae07f54c7454fe72,subnet-0d2d334cbe1467f4b],securityGroups=[sg-0ebf38ea0618aef2d],assignPublicIp=DISABLED}" \
     --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e,containerName=busyb-google-workspace-mcp,containerPort=8000" \
     --service-registries "registryArn=arn:aws:servicediscovery:us-east-1:758888582357:service/srv-gxethbb34gto3cbr,containerName=busyb-google-workspace-mcp,containerPort=8000" \
     --enable-execute-command \
     --health-check-grace-period-seconds 60 \
     --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100" \
     --region us-east-1
   ```

3. **Monitor Service Startup**:
   ```bash
   # Wait for service to stabilize
   aws ecs wait services-stable \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1

   # Check service status
   aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1
   ```

#### Continuous Deployment (GitHub Actions)

After initial setup, deployments are automated via GitHub Actions:

1. **Trigger**: Push to `main` branch
2. **Build**: Docker image built and tagged with commit SHA
3. **Push**: Image pushed to ECR
4. **Deploy**: GitHub Actions updates ECS service with new image

**GitHub Actions Workflow** (`.github/workflows/deploy-ecs.yml`):
- Authenticates with AWS using OIDC (no long-lived credentials)
- Builds Docker image with production optimizations
- Pushes image to ECR with commit SHA and `latest` tags
- Registers new task definition revision
- Updates ECS service to use new task definition
- Waits for deployment to stabilize

**Deployment Commands**:
```bash
# GitHub Actions runs these commands automatically
aws ecs register-task-definition --cli-input-json file://task-definition.json
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:REVISION \
  --force-new-deployment
```

### Monitoring and Health Checks

#### CloudWatch Metrics

**ECS Service Metrics**:
- **CPUUtilization**: Average CPU usage across tasks
- **MemoryUtilization**: Average memory usage across tasks
- **DesiredTaskCount**: Number of tasks that should be running
- **RunningTaskCount**: Number of tasks currently running

**ALB Target Group Metrics**:
- **HealthyHostCount**: Number of healthy targets
- **UnHealthyHostCount**: Number of unhealthy targets
- **TargetResponseTime**: Response time from targets
- **RequestCount**: Number of requests to target group

**Viewing Metrics**:
```bash
# CPU utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1

# Memory utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

#### Health Check Status

**Check Service Health**:
```bash
# Service overview
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:5]}' \
  --region us-east-1

# Task health status
TASK_ARN=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text \
  --region us-east-1)

aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks ${TASK_ARN} \
  --query 'tasks[0].{Health:healthStatus,LastStatus:lastStatus,Containers:containers[0].healthStatus}' \
  --region us-east-1

# ALB target health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e \
  --region us-east-1
```

**Health Status Values**:
- **HEALTHY**: Task is passing health checks
- **UNHEALTHY**: Task is failing health checks
- **UNKNOWN**: Health status not yet determined (during startup)

### Troubleshooting

For detailed troubleshooting procedures, see the [Operations Guide](./operations.md).

**Common Issues**:
- Task fails to start → Check CloudWatch logs for application errors
- Health checks failing → Verify health endpoint is responding on port 8000
- Service not accessible via ALB → Check path prefix issue and listener rules
- OAuth errors → Verify secrets in Secrets Manager and S3 bucket access

**Quick Checks**:
```bash
# View recent logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 5m --region us-east-1

# Check task stopped reason
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks $(aws ecs list-tasks --cluster busyb-cluster --service-name busyb-google-workspace-mcp-service --desired-status STOPPED --region us-east-1 --query 'taskArns[0]' --output text) \
  --query 'tasks[0].{StoppedReason:stoppedReason,Containers:containers[0].{ExitCode:exitCode,Reason:reason}}' \
  --region us-east-1

# Test health endpoint from within VPC
curl http://google-workspace.busyb.local:8000/health
```

### Scaling

#### Manual Scaling

Update the desired task count:

```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 2 \
  --region us-east-1
```

#### Auto Scaling (Optional)

Configure auto scaling based on CPU or memory utilization:

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --min-capacity 1 \
  --max-capacity 4 \
  --region us-east-1

# Create scaling policy based on CPU
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --policy-name busyb-google-workspace-cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{"TargetValue":70.0,"PredefinedMetricSpecification":{"PredefinedMetricType":"ECSServiceAverageCPUUtilization"}}' \
  --region us-east-1
```

### Cost Considerations

**Fargate Pricing** (per task, per hour):
- **CPU**: 0.5 vCPU × $0.04048/vCPU-hour = ~$0.02024/hour
- **Memory**: 1 GB × $0.004445/GB-hour = ~$0.004445/hour
- **Total per task**: ~$0.025/hour = ~$18/month

**Additional Costs**:
- **CloudWatch Logs**: ~$0.50/GB ingested + $0.03/GB stored
- **ALB**: ~$22/month + $0.008/LCU-hour
- **NAT Gateway**: ~$32/month + $0.045/GB data processed
- **S3**: ~$0.023/GB/month (minimal for OAuth tokens)
- **Secrets Manager**: ~$0.40/secret/month

**Total Estimated Monthly Cost**: ~$75-100/month (with 1 task running 24/7)

---

## Additional Resources

- [Configuration Guide](./configuration.md) - Environment variable reference
- [Authentication Guide](./authentication.md) - OAuth setup and S3 storage
- [Operations Guide](./operations.md) - Operational procedures and troubleshooting
- [Docker Compose Usage](./docker-compose-usage.md) - Local development guide
- [Architecture Documentation](./architecture.md) - System design details

---

**Last Updated**: 2025-11-12 (Phase 4 CI/CD - Task 4.9)
