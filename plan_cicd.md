# CI/CD Pipeline Implementation Plan for Google Workspace MCP Server

## Overview

This plan outlines the implementation of a GitHub Actions-based CI/CD pipeline for deploying the Google Workspace MCP server to AWS ECS Fargate. This server will be deployed to the **same production environment** as the other BusyB services (same VPC, same AWS account, same secrets infrastructure).

## Scope

**INCLUDED (MVP + CI/CD):**
- ✅ Integration with existing BusyB AWS infrastructure (VPC, security groups, secrets) - **PHASE 1 COMPLETE**
- ✅ Dockerfile optimization (already exists, minor refinements needed) - **PHASE 2 COMPLETE**
- ✅ GitHub Actions workflow for automated builds and deployments - **PHASE 3 COMPLETE**
- ✅ ECS Fargate service with health checks - **PHASE 4 COMPLETE**
- ✅ S3 credential storage integration (existing bucket) - **PHASE 4 COMPLETE**
- ✅ Service discovery integration for Core Agent communication - **PHASE 4 COMPLETE**
- ✅ Integration testing and production documentation - **PHASE 5 COMPLETE**

**DEFERRED (Future Phases):**
- ⏸️ Multi-AZ deployment and high availability
- ⏸️ Advanced monitoring and CloudWatch alarms
- ⏸️ Auto-scaling policies
- ⏸️ Blue/green deployments

## Component to Deploy

**Google Workspace MCP Server** (`google_workspace_mcp/`) - FastMCP server providing Google Workspace API integrations:
- Gmail, Drive, Calendar, Docs, Sheets, Slides, Forms, Tasks, Chat, Search tools
- OAuth 2.0/2.1 authentication with PKCE
- S3-based credential storage (shared with other services)
- Streamable HTTP transport for MCP protocol

## Phase 1: Prerequisites & AWS Setup

### 1.1 AWS Infrastructure Reuse (Existing Resources)

**Resources to Reuse:**
- ✅ VPC with public/private subnets
- ✅ Aurora Serverless v2 PostgreSQL cluster (for session data if needed)
- ✅ S3 bucket for OAuth tokens (shared with QuickBooks/Jobber MCP servers)
- ✅ AWS Secrets Manager (add Google OAuth credentials)
- ✅ Application Load Balancer (ALB) - add new target group
- ✅ Security groups (ECS, ALB) - reuse existing
- ✅ NAT Gateway for external API access

**New Resources Needed:**
- [ ] ECR repository for `busyb-google-workspace-mcp`
- [ ] ECS service for Google Workspace MCP
- [ ] Target group for ALB (port 8000)
- [ ] AWS Secrets Manager entries for Google OAuth credentials
- [ ] CloudWatch Log Group for container logs

### 1.2 ECR Repository Setup

```bash
aws ecr create-repository --repository-name busyb-google-workspace-mcp
```

**Configuration:**
- Enable vulnerability scanning
- Set lifecycle policy (keep last 10 images)

```bash
aws ecr put-lifecycle-policy \
  --repository-name busyb-google-workspace-mcp \
  --lifecycle-policy-text '{
    "rules": [{
      "rulePriority": 1,
      "description": "Keep last 10 images",
      "selection": {
        "tagStatus": "any",
        "countType": "imageCountMoreThan",
        "countNumber": 10
      },
      "action": {
        "type": "expire"
      }
    }]
  }'
```

### 1.3 GitHub Secrets Configuration

**Add to GitHub repository** (`Settings > Secrets and variables > Actions`):

```
# Reuse existing AWS credentials
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=<your-account-id>
AWS_ACCESS_KEY_ID=<iam-user-key>
AWS_SECRET_ACCESS_KEY=<iam-user-secret>
ECR_REGISTRY=<account-id>.dkr.ecr.us-east-1.amazonaws.com

# ECS Configuration (reuse existing cluster)
ECS_CLUSTER=busyb-cluster
ECS_SERVICE_GOOGLE_WORKSPACE=busyb-google-workspace-mcp-service
```

**Note:** The IAM policy for GitHub Actions should already allow ECR and ECS operations for the existing cluster.

### 1.4 AWS Secrets Manager Configuration

**Add new secrets for Google OAuth:**

```bash
# Google OAuth Client ID
aws secretsmanager create-secret \
  --name busyb/google-oauth-client-id \
  --secret-string "your-google-client-id.apps.googleusercontent.com"

# Google OAuth Client Secret
aws secretsmanager create-secret \
  --name busyb/google-oauth-client-secret \
  --secret-string "your-google-client-secret"
```

**Reuse existing secrets:**
- `busyb/s3-credentials-bucket` - S3 bucket name for OAuth credentials storage
- AWS IAM role with S3 access (existing)

## Phase 2: Dockerfile Review & Optimization

### 2.1 Current Dockerfile Status

**Existing Dockerfile** (`Dockerfile`) is well-structured with:
- ✅ Python 3.12-slim base image
- ✅ Multi-stage dependency installation with `uv`
- ✅ Non-root user for security
- ✅ Health check endpoint
- ✅ Environment variable support
- ✅ Debug logging for troubleshooting

**Minor Refinements Needed:**
- [ ] Remove debug RUN statements (lines 25-40, 58-59) for production
- [ ] Add AWS CLI for credential management (optional, boto3 is sufficient)
- [ ] Ensure PORT environment variable defaults to 8000

### 2.2 Production-Ready Dockerfile

**File:** `Dockerfile` (updated for production)

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Copy all application code (needed for uv sync with local package)
COPY . .

# Install Python dependencies using uv sync
RUN uv sync --frozen --no-dev

# Final stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY . .

# Activate virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Default port (can be overridden by environment variable)
ENV PORT=8000
ENV WORKSPACE_MCP_PORT=8000
ENV WORKSPACE_MCP_BASE_URI=http://localhost

# Create placeholder client_secrets.json for lazy loading
RUN echo '{"installed":{"client_id":"placeholder","client_secret":"placeholder","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","redirect_uris":["http://localhost:8000/oauth2callback"]}}' > /app/client_secrets.json

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Command to run the application
CMD ["uv", "run", "main.py", "--transport", "streamable-http"]
```

### 2.3 Verify .dockerignore

**File:** `.dockerignore` (already exists and is well-configured)

Current `.dockerignore` already excludes:
- ✅ Git files and version control
- ✅ Documentation and notes
- ✅ Test files and coverage
- ✅ Build artifacts
- ✅ Credentials directory
- ✅ Cache and temporary files
- ✅ IDE files

**No changes needed.**

## Phase 3: GitHub Actions Workflow

### 3.1 CI/CD Workflow for Google Workspace MCP

**File:** `.github/workflows/deploy-google-workspace-mcp.yml`

```yaml
name: Deploy Google Workspace MCP to AWS ECS

on:
  push:
    branches: [main]
    paths:
      - 'auth/**'
      - 'core/**'
      - 'gcalendar/**'
      - 'gchat/**'
      - 'gdocs/**'
      - 'gdrive/**'
      - 'gforms/**'
      - 'gmail/**'
      - 'gsearch/**'
      - 'gsheets/**'
      - 'gslides/**'
      - 'gtasks/**'
      - 'main.py'
      - 'pyproject.toml'
      - 'uv.lock'
      - 'Dockerfile'
      - '.dockerignore'
      - '.github/workflows/deploy-google-workspace-mcp.yml'
  workflow_dispatch: # Allow manual triggers

env:
  AWS_REGION: us-east-1
  ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
  ECR_REPOSITORY: busyb-google-workspace-mcp

jobs:
  build-and-deploy:
    name: Build and Deploy Google Workspace MCP
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push Docker image
        env:
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} .
          docker tag ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} \
                     ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest
          docker push ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }}
          docker push ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest

      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster ${{ secrets.ECS_CLUSTER }} \
            --service ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
            --force-new-deployment \
            --region ${{ env.AWS_REGION }}

      - name: Wait for service stability
        run: |
          aws ecs wait services-stable \
            --cluster ${{ secrets.ECS_CLUSTER }} \
            --services ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
            --region ${{ env.AWS_REGION }}
```

**Key Features:**
- Triggered only when relevant files change (efficient CI)
- Manual trigger support via `workflow_dispatch`
- Builds and pushes Docker image to ECR
- Forces new deployment to ECS
- Waits for service to stabilize before completing

## Phase 4: ECS Task Definition & Service

### 4.1 ECS Task Definition

**File:** `ecs/task-definition-google-workspace-mcp.json`

```json
{
  "family": "busyb-google-workspace-mcp",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<account-id>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<account-id>:role/busyb-mcp-task-role",
  "containerDefinitions": [
    {
      "name": "busyb-google-workspace-mcp",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "essential": true,
      "environment": [
        {
          "name": "PORT",
          "value": "8000"
        },
        {
          "name": "WORKSPACE_MCP_PORT",
          "value": "8000"
        },
        {
          "name": "WORKSPACE_MCP_BASE_URI",
          "value": "http://google-workspace.busyb.local"
        },
        {
          "name": "MCP_ENABLE_OAUTH21",
          "value": "true"
        },
        {
          "name": "MCP_SINGLE_USER_MODE",
          "value": "0"
        },
        {
          "name": "OAUTHLIB_INSECURE_TRANSPORT",
          "value": "0"
        }
      ],
      "secrets": [
        {
          "name": "MCP_GOOGLE_OAUTH_CLIENT_ID",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:busyb/google-oauth-client-id"
        },
        {
          "name": "MCP_GOOGLE_OAUTH_CLIENT_SECRET",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:busyb/google-oauth-client-secret"
        },
        {
          "name": "MCP_GOOGLE_CREDENTIALS_DIR",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:<account-id>:secret:busyb/s3-credentials-bucket"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/busyb-google-workspace-mcp",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

**Key Environment Variable Naming:**
- `MCP_GOOGLE_OAUTH_CLIENT_ID` - Follows existing MCP naming convention
- `MCP_GOOGLE_OAUTH_CLIENT_SECRET` - Follows existing MCP naming convention
- `MCP_GOOGLE_CREDENTIALS_DIR` - S3 path for credential storage (e.g., `s3://busyb-oauth-tokens/google/`)

**Note:** The task role (`busyb-mcp-task-role`) should already have S3 permissions for the shared credentials bucket.

### 4.2 IAM Task Role Permissions

**Verify existing IAM role** (`busyb-mcp-task-role`) includes:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::busyb-oauth-tokens/*",
        "arn:aws:s3:::busyb-oauth-tokens"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:*:secret:busyb/*"
      ]
    }
  ]
}
```

### 4.3 CloudWatch Log Group Creation

```bash
aws logs create-log-group --log-group-name /ecs/busyb-google-workspace-mcp --region us-east-1
```

**Set retention policy** (30 days for MVP):
```bash
aws logs put-retention-policy \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --retention-in-days 30
```

### 4.4 ECS Service Creation

```bash
aws ecs create-service \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxx],
    securityGroups=[sg-xxx],
    assignPublicIp=DISABLED
  }" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/busyb-google-workspace/xxx,containerName=busyb-google-workspace-mcp,containerPort=8000" \
  --service-registries "registryArn=arn:aws:servicediscovery:us-east-1:<account-id>:service/srv-xxx,containerName=busyb-google-workspace-mcp,containerPort=8000" \
  --enable-execute-command \
  --region us-east-1
```

**Service Discovery Configuration:**
- Service name: `google-workspace.busyb.local`
- Allows Core Agent to reach MCP server at `http://google-workspace.busyb.local:8000/mcp`

**Note:** Start with `desired-count 1` for MVP to minimize costs.

## Phase 5: Integration with Core Agent

### 5.1 Core Agent Configuration

**Update Core Agent environment variables** to include Google Workspace MCP server:

```json
{
  "name": "MCP_GOOGLE_WORKSPACE_URL",
  "value": "http://google-workspace.busyb.local:8000/mcp"
}
```

**Core Agent should be configured to:**
- Connect to Google Workspace MCP via service discovery
- Use streamable-http transport for MCP protocol
- Handle OAuth authentication callbacks if proxying to users

### 5.2 ALB Target Group Configuration

**Create target group for Google Workspace MCP:**

```bash
aws elbv2 create-target-group \
  --name busyb-google-workspace \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxx \
  --target-type ip \
  --health-check-enabled \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --health-check-timeout-seconds 5 \
  --healthy-threshold-count 2 \
  --unhealthy-threshold-count 3
```

**Add listener rule to ALB** (if external access needed):

```bash
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:us-east-1:<account-id>:listener/app/busyb-alb/xxx \
  --priority 50 \
  --conditions Field=path-pattern,Values='/google-workspace/*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:<account-id>:targetgroup/busyb-google-workspace/xxx
```

## Phase 6: Environment Variable Mapping

### 6.1 Google Workspace MCP Environment Variables

The server expects environment variables in the format `GOOGLE_*`, but we'll inject them as `MCP_GOOGLE_*` in ECS for consistency with other MCP servers.

**Mapping in Dockerfile or entrypoint script:**

Add to Dockerfile CMD or create entrypoint script:

```bash
#!/bin/bash
set -e

# Map MCP_GOOGLE_* environment variables to GOOGLE_* for compatibility
export GOOGLE_OAUTH_CLIENT_ID="${MCP_GOOGLE_OAUTH_CLIENT_ID}"
export GOOGLE_OAUTH_CLIENT_SECRET="${MCP_GOOGLE_OAUTH_CLIENT_SECRET}"
export GOOGLE_MCP_CREDENTIALS_DIR="${MCP_GOOGLE_CREDENTIALS_DIR}"

# Run the application
exec uv run main.py --transport streamable-http "$@"
```

**Update Dockerfile to use entrypoint:**

```dockerfile
# ... existing Dockerfile content ...

# Copy entrypoint script
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown app:app /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
```

### 6.2 Environment Variable Reference

| ECS Variable (Injected) | Server Variable (Expected) | Source |
|------------------------|---------------------------|--------|
| `MCP_GOOGLE_OAUTH_CLIENT_ID` | `GOOGLE_OAUTH_CLIENT_ID` | Secrets Manager |
| `MCP_GOOGLE_OAUTH_CLIENT_SECRET` | `GOOGLE_OAUTH_CLIENT_SECRET` | Secrets Manager |
| `MCP_GOOGLE_CREDENTIALS_DIR` | `GOOGLE_MCP_CREDENTIALS_DIR` | Secrets Manager (S3 path) |
| `PORT` | `PORT` | Task Definition |
| `WORKSPACE_MCP_PORT` | `WORKSPACE_MCP_PORT` | Task Definition |
| `WORKSPACE_MCP_BASE_URI` | `WORKSPACE_MCP_BASE_URI` | Task Definition |
| `MCP_ENABLE_OAUTH21` | `MCP_ENABLE_OAUTH21` | Task Definition |

## Implementation Timeline (Simplified)

### Week 1: AWS Infrastructure & Secrets

- [x] Verify existing VPC, subnets, security groups are compatible
- [ ] Create ECR repository for `busyb-google-workspace-mcp`
- [ ] Add Google OAuth credentials to AWS Secrets Manager
- [ ] Create CloudWatch Log Group
- [ ] Create ALB target group for Google Workspace MCP
- [ ] Verify S3 bucket permissions for credential storage

### Week 2: Dockerfile & GitHub Actions

- [x] Create production-ready Dockerfile (remove debug statements) ✅ PHASE 2 COMPLETE
- [x] Create `docker-entrypoint.sh` for environment variable mapping ✅ PHASE 2 COMPLETE
- [ ] Add GitHub secrets (AWS credentials, service names)
- [ ] Create `.github/workflows/deploy-google-workspace-mcp.yml`
- [x] Test Docker build locally ✅ PHASE 2 COMPLETE
- [ ] Test GitHub Actions workflow (manual trigger)

### Week 3: ECS Task Definition & Service

- [ ] Create ECS task definition JSON file
- [ ] Register task definition with ECS
- [ ] Create ECS service with ALB integration
- [ ] Set up AWS Cloud Map service discovery
- [ ] Verify health checks pass
- [ ] Test connectivity from Core Agent

### Week 4: Integration & Testing

- [ ] Update Core Agent configuration to use Google Workspace MCP
- [ ] Push to `main` branch to trigger automated deployment
- [ ] Verify service is running and healthy
- [ ] Test end-to-end OAuth flow (authenticate with Google)
- [ ] Test Gmail, Drive, Calendar tools via Core Agent
- [ ] Verify S3 credential storage works
- [ ] Document any deployment issues and fixes

## Success Criteria (MVP)

✅ **Google Workspace MCP deployed to AWS ECS Fargate**
✅ **Automated deployment:** Push to `main` triggers build and deploy
✅ **Health checks pass:** Container reports healthy
✅ **S3 credential storage works:** User credentials stored in shared S3 bucket
✅ **Service discovery works:** Core Agent can connect via `http://google-workspace.busyb.local:8000/mcp`
✅ **OAuth authentication works:** Users can authenticate with Google and use tools
✅ **Basic monitoring:** Can view logs in CloudWatch

## Quick Rollback Procedure (Manual)

If a deployment breaks the system:

```bash
# 1. Get previous task definition revision
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].deployments[1].taskDefinition'

# 2. Update service to previous revision
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:PREVIOUS_REVISION_NUMBER
```

## Security Considerations

### OAuth Credential Storage

- **S3 Encryption:** Server-side encryption (SSE-S3 AES256) enabled on shared bucket
- **IAM Access Control:** Task role has minimum required permissions
- **Credential Isolation:** Each user's credentials stored at `s3://busyb-oauth-tokens/google/{email}.json`

### Network Security

- **Private Subnets:** ECS tasks run in private subnets (no direct internet access)
- **NAT Gateway:** External API calls to Google routed through NAT Gateway
- **Security Groups:** Only allow traffic from ALB and Core Agent
- **Service Discovery:** Internal DNS resolution (no public exposure)

### Secrets Management

- **AWS Secrets Manager:** OAuth client credentials never committed to code
- **Environment Variable Injection:** Secrets injected at runtime via ECS task definition
- **Least Privilege:** Task execution role only has access to required secrets

## What Comes Next (Post-MVP)

After the MVP is running, we'll revisit production hardening:
- Multi-AZ deployment for high availability
- CloudWatch alarms for service health and errors
- Auto-scaling policies based on CPU/memory usage
- Blue/green deployments for zero-downtime updates
- Enhanced logging and distributed tracing
- Cost optimization strategies

---

**Note:** This plan leverages the existing BusyB infrastructure and follows the same patterns as the other MCP servers for consistency and ease of maintenance.
