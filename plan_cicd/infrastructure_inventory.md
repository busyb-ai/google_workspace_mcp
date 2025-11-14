# BusyB AWS Infrastructure Inventory

**Date**: 2025-11-12
**AWS Account ID**: 758888582357
**AWS Region**: us-east-1
**Purpose**: Infrastructure inventory for Google Workspace MCP deployment

---

## Summary

This document contains verified resource IDs and configurations for the existing BusyB AWS infrastructure. All resources listed below have been verified as active and accessible as of the date above.

---

## Network Infrastructure

### VPC
- **VPC ID**: vpc-0111b7630bcb61b61
- **CIDR Block**: 10.0.0.0/16
- **Name**: busyb-vpc
- **Status**: Available

### Subnets

#### Public Subnets
| Subnet ID | CIDR Block | Availability Zone | Name |
|-----------|------------|-------------------|------|
| subnet-07f1ff5451a4a7b86 | 10.0.1.0/24 | us-east-1a | busyb-public-subnet-1a |
| subnet-0bfe170fb995b44b0 | 10.0.2.0/24 | us-east-1b | busyb-public-subnet-1b |

#### Private Subnets
| Subnet ID | CIDR Block | Availability Zone | Name |
|-----------|------------|-------------------|------|
| subnet-0d2d334cbe1467f4b | 10.0.10.0/24 | us-east-1a | busyb-private-subnet-1a |
| subnet-0ae07f54c7454fe72 | 10.0.11.0/24 | us-east-1b | busyb-private-subnet-1b |

### Internet Gateway
- **IGW ID**: igw-0f880ca971abff6d3
- **Name**: busyb-igw
- **Attached to VPC**: vpc-0111b7630bcb61b61

### NAT Gateway
- **NAT Gateway ID**: nat-0e31233b2d4d71756
- **Name**: busyb-nat-gw
- **Status**: available
- **Subnet**: subnet-07f1ff5451a4a7b86 (busyb-public-subnet-1a)

### Route Tables

#### Public Route Table
- **Route Table ID**: rtb-00ba21c091f8077b9
- **Name**: busyb-public-rt
- **Associated Subnets**:
  - subnet-07f1ff5451a4a7b86 (busyb-public-subnet-1a)
  - subnet-0bfe170fb995b44b0 (busyb-public-subnet-1b)
- **Routes**: Internet Gateway (igw-0f880ca971abff6d3)

#### Private Route Table
- **Route Table ID**: rtb-07e300e9a43748768
- **Name**: busyb-private-rt
- **Associated Subnets**:
  - subnet-0d2d334cbe1467f4b (busyb-private-subnet-1a)
  - subnet-0ae07f54c7454fe72 (busyb-private-subnet-1b)
- **Routes**: NAT Gateway (nat-0e31233b2d4d71756)

### Security Groups

| Security Group ID | Name | Description | Purpose |
|------------------|------|-------------|---------|
| sg-0b5d6bf9cab3a6a83 | busyb-alb-sg | Allow HTTPS and HTTP from internet | ALB ingress |
| sg-0ebf38ea0618aef2d | busyb-ecs-sg | Allow traffic from ALB and internal services | ECS tasks |
| sg-01cc83676f64d8b83 | busyb-rds-sg | Allow PostgreSQL from ECS tasks | RDS database |
| sg-014a1fede5eb05d8a | busyb-redis-sg | Allow Redis from ECS tasks | ElastiCache Redis |

#### ALB Security Group Rules (sg-0b5d6bf9cab3a6a83)
**Ingress**:
- Port 80 (HTTP) from 0.0.0.0/0
- Port 443 (HTTPS) from 0.0.0.0/0

#### ECS Security Group Rules (sg-0ebf38ea0618aef2d)
**Ingress**:
- Ports 8000-8080 (TCP) from ALB security group

---

## Load Balancer

### Application Load Balancer
- **Name**: busyb-alb
- **ARN**: arn:aws:elasticloadbalancing:us-east-1:758888582357:loadbalancer/app/busyb-alb/5111c2db275a2af3
- **DNS Name**: busyb-alb-1791678277.us-east-1.elb.amazonaws.com
- **Type**: application
- **Scheme**: internet-facing
- **VPC**: vpc-0111b7630bcb61b61

### ALB Listeners

| Port | Protocol | Default Action | Listener ARN |
|------|----------|----------------|--------------|
| 80 | HTTP | Redirect to HTTPS | arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/48a2bc40233f70ba |
| 443 | HTTPS | Forward to target group | arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23 |

### SSL Certificate
- **Certificate ARN**: arn:aws:acm:us-east-1:758888582357:certificate/f0d9ff36-0ab5-4348-bcac-7f5aef60da05
- **Domain**: busyb.ai
- **Subject Alternative Names**: busyb.ai, *.busyb.ai
- **Status**: ISSUED
- **Type**: AMAZON_ISSUED

### Target Groups

| Name | ARN | Port | Protocol | Health Check Path |
|------|-----|------|----------|-------------------|
| busyb-core-agent-tg | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-core-agent-tg/314ebb2e3f3db167 | 8000 | HTTP | /health |
| busyb-database-api-tg | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-database-api-tg/579f02c50f2fc40b | 8001 | HTTP | /health |
| busyb-jobber-mcp-tg | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-jobber-mcp-tg/be679804644c1224 | 8080 | HTTP | /health |
| busyb-quickbooks-mcp-tg | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-quickbooks-mcp-tg/c4134175bb7897e4 | 8080 | HTTP | /health |
| busyb-research-mcp-tg | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-research-mcp-tg/beae21c33696fdbc | 8080 | HTTP | /health |
| busyb-google-workspace | arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e | 8000 | HTTP | /health |

### ALB Routing Rules (HTTPS Listener)

| Priority | Path Pattern | Target Group | Rule ARN |
|----------|--------------|--------------|----------|
| 1 | /mcp/quickbooks* | busyb-quickbooks-mcp-tg | - |
| 2 | /mcp/jobber* | busyb-jobber-mcp-tg | - |
| 3 | /mcp/research* | busyb-research-mcp-tg | - |
| 4 | /api/db* | busyb-database-api-tg | - |
| 50 | /google-workspace/* | busyb-google-workspace | arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4 |
| default | (all others) | busyb-core-agent-tg | - |

**Listener Rule Details (Priority 50)**:
- **Rule ARN**: arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4
- **Path Pattern**: `/google-workspace/*`
- **Action**: Forward to `busyb-google-workspace` target group
- **Target Group Weight**: 1
- **Stickiness**: Disabled
- **Created**: 2025-11-12 (Task 4.4)

---

## ECS Infrastructure

### ECS Cluster
- **Cluster Name**: busyb-cluster
- **Cluster ARN**: arn:aws:ecs:us-east-1:758888582357:cluster/busyb-cluster
- **Status**: ACTIVE
- **Running Tasks**: 5
- **Pending Tasks**: 0
- **Launch Type**: FARGATE

### Existing ECS Services

| Service Name | ARN | Desired Count | Status |
|--------------|-----|---------------|--------|
| busyb-core-agent-service | arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-core-agent-service | 1 | ACTIVE |
| busyb-database-api-service | arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-database-api-service | 1 | ACTIVE |
| busyb-jobber-mcp-service | arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-jobber-mcp-service | 1 | ACTIVE |
| busyb-quickbooks-mcp-service | arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-quickbooks-mcp-service | 1 | ACTIVE |
| busyb-research-mcp-service | arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-research-mcp-service | 1 | ACTIVE |

### Example Task Definition (busyb-jobber-mcp:2)
**Reference for new Google Workspace MCP task definition**:
- **Task Role ARN**: arn:aws:iam::758888582357:role/busyb-jobber-mcp-task-role
- **Execution Role ARN**: arn:aws:iam::758888582357:role/ecsTaskExecutionRole
- **CPU**: 256 (0.25 vCPU)
- **Memory**: 512 MB
- **Network Mode**: awsvpc
- **Launch Type**: FARGATE
- **Container Port**: 8080
- **Log Driver**: awslogs
- **Log Group**: /ecs/busyb-jobber-mcp
- **Log Stream Prefix**: ecs

---

## Container Registry (ECR)

### Existing Repositories

| Repository Name | Repository URI | Status |
|----------------|----------------|--------|
| busyb-core-agent | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-core-agent | Active |
| busyb-database-api | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-database-api | Active |
| busyb-jobber-mcp | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-jobber-mcp | Active |
| busyb-quickbooks-mcp | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-quickbooks-mcp | Active |
| busyb-research-mcp | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-research-mcp | Active |
| busyb-google-workspace-mcp | 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp | Active |

### Google Workspace MCP Repository Details
- **Repository Name**: busyb-google-workspace-mcp
- **Repository URI**: 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp
- **Repository ARN**: arn:aws:ecr:us-east-1:758888582357:repository/busyb-google-workspace-mcp
- **Image Scanning**: Enabled (scanOnPush=true)
- **Encryption**: AES256
- **Lifecycle Policy**: Keep last 10 images
- **Created**: 2025-11-12

---

## Storage (S3)

### S3 Bucket for OAuth Tokens
- **Bucket Name**: busyb-oauth-tokens-758888582357
- **Region**: us-east-1
- **Encryption**: Enabled (AWS KMS with aws/s3 key)
- **Bucket Key**: Enabled
- **Versioning**: Not enabled
- **Contents**: tokens/ directory
- **Access**: Private

**S3 Bucket ARN**: arn:aws:s3:::busyb-oauth-tokens-758888582357

---

## IAM Roles & Policies

### ECS Task Execution Role
- **Role Name**: ecsTaskExecutionRole
- **Role ARN**: arn:aws:iam::758888582357:role/ecsTaskExecutionRole
- **Description**: ECS task execution role for pulling images and accessing secrets
- **Attached Policies**:
  - AmazonECSTaskExecutionRolePolicy (AWS managed)
  - SecretsManagerReadWrite (AWS managed)

**Purpose**: Used by ECS to pull container images from ECR and retrieve secrets from Secrets Manager.

### Existing Task Roles

| Role Name | Role ARN | Purpose |
|-----------|----------|---------|
| busyb-core-agent-task-role | arn:aws:iam::758888582357:role/busyb-core-agent-task-role | Core agent permissions |
| busyb-database-api-task-role | arn:aws:iam::758888582357:role/busyb-database-api-task-role | Database API permissions |
| busyb-jobber-mcp-task-role | arn:aws:iam::758888582357:role/busyb-jobber-mcp-task-role | Jobber MCP permissions |
| busyb-quickbooks-mcp-task-role | arn:aws:iam::758888582357:role/busyb-quickbooks-mcp-task-role | QuickBooks MCP permissions |
| busyb-research-mcp-task-role | arn:aws:iam::758888582357:role/busyb-research-mcp-task-role | Research MCP permissions |
| busyb-google-workspace-mcp-task-role | arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role | **Google Workspace MCP permissions** ✓ |

### Example Task Role Policy (busyb-jobber-mcp-task-role)
**Policy Name**: busyb-jobber-mcp-policy

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
            "Resource": "arn:aws:s3:::busyb-oauth-tokens-758888582357/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": [
                "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/*"
            ]
        }
    ]
}
```

### Google Workspace MCP Task Role Policy
**Role Name**: busyb-google-workspace-mcp-task-role
**Role ARN**: arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role
**Policy Name**: busyb-google-workspace-mcp-policy
**Created**: 2025-11-12

This role grants the Google Workspace MCP service permissions to access S3 for OAuth token storage and Secrets Manager for configuration secrets.

**Key Differences from Other MCP Services**:
- Includes `s3:ListBucket` permission (required for listing credential files in S3)
- Separate statement for bucket-level `ListBucket` operation (applies to bucket ARN)
- Object-level operations (`GetObject`, `PutObject`, `DeleteObject`) apply to bucket contents

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
      "Resource": "arn:aws:s3:::busyb-oauth-tokens-758888582357/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::busyb-oauth-tokens-758888582357"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/*"
      ]
    }
  ]
}
```

**Policy Document Location**: `plan_cicd/task-role-policy.json`

### GitHub Actions IAM User

**To Be Created for Task 1.4**:

| IAM User Name | Purpose | Required Policies |
|---------------|---------|-------------------|
| github-actions-google-workspace-mcp | CI/CD deployment via GitHub Actions | Custom policy (see below) |

**IAM Policy for GitHub Actions** (`GitHubActionsGoogleWorkspaceMCPPolicy`):

This policy grants the minimum permissions needed for GitHub Actions to:
1. Authenticate with ECR and push Docker images
2. Register new ECS task definitions
3. Update the ECS service to deploy new task definitions
4. Pass IAM roles to ECS tasks

**Key Permissions**:
- **ECR**: `GetAuthorizationToken`, `BatchCheckLayerAvailability`, `GetDownloadUrlForLayer`, `BatchGetImage`, `PutImage`, `InitiateLayerUpload`, `UploadLayerPart`, `CompleteLayerUpload`
- **ECS**: `UpdateService`, `DescribeServices`, `DescribeTaskDefinition`, `RegisterTaskDefinition`
- **IAM**: `PassRole` (restricted to ECS task execution and task roles only)

**Resources Restricted To**:
- ECR Repository: `arn:aws:ecr:us-east-1:758888582357:repository/busyb-google-workspace-mcp`
- ECS Service: `arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-google-workspace-mcp-service`
- ECS Cluster: `arn:aws:ecs:us-east-1:758888582357:cluster/busyb-cluster`
- Task Definition: `arn:aws:ecs:us-east-1:758888582357:task-definition/busyb-google-workspace-mcp:*`
- Task Execution Role: `arn:aws:iam::758888582357:role/ecsTaskExecutionRole`
- Task Role: `arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role`

**Full policy JSON**: See `plan_cicd/github_secrets_setup.md` for complete policy document.

**Security Notes**:
- Access keys should be rotated every 90 days
- CloudTrail should be enabled to audit API calls
- User has no console access (programmatic access only)
- Follows principle of least privilege

---

## Secrets Manager

### Existing Secrets

| Secret Name | Secret ARN | Purpose |
|-------------|------------|---------|
| busyb/anthropic-api-key | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/anthropic-api-key-20hFNt | Anthropic API access |
| busyb/google-oauth-client-id | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx | **Google OAuth Client ID** ✓ |
| busyb/google-oauth-client-secret | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z | **Google OAuth Client Secret** ✓ |
| busyb/s3-credentials-bucket | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM | **S3 bucket path for credential storage** ✓ |
| busyb/groq-api-key | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/groq-api-key-C2JcpV | Groq API access |
| busyb/jobber-oauth-client-id | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/jobber-oauth-client-id-pG2OB5 | Jobber OAuth Client ID |
| busyb/jobber-oauth-client-secret | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/jobber-oauth-client-secret-Zhfft0 | Jobber OAuth Client Secret |
| busyb/openai-api-key | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/openai-api-key-LiBkvo | OpenAI API access |
| busyb/postgres-url | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/postgres-url-jp2RqO | PostgreSQL connection string |
| busyb/quickbooks-oauth-client-id | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/quickbooks-oauth-client-id-H8sOK4 | QuickBooks OAuth Client ID |
| busyb/quickbooks-oauth-client-secret | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/quickbooks-oauth-client-secret-WqzBVJ | QuickBooks OAuth Client Secret |
| busyb/serpapi-api-key | arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/serpapi-api-key-thWciJ | SerpAPI access |

**Status**: ✓ Google OAuth credentials and S3 bucket path already exist in Secrets Manager.

**Important Notes**:
- Google OAuth secrets created on 2025-10-28
- S3 credentials bucket secret created on 2025-11-12
- OAuth secrets are stored as JSON objects with keys (see `deployment_action_items.md` for details)
- S3 bucket path is stored as plain string: `s3://busyb-oauth-tokens-758888582357/`
- Manual verification of OAuth credential values recommended (see `deployment_action_items.md`)

---

## CloudWatch Logs

### Existing Log Groups

| Log Group Name | Retention (Days) | Stored Bytes | Purpose |
|----------------|------------------|--------------|---------|
| /ecs/busyb-core-agent | 7 | 3,794,841 | Core agent logs |
| /ecs/busyb-database-api | 7 | 2,943,505 | Database API logs |
| /ecs/busyb-jobber-mcp | 7 | 5,150,277 | Jobber MCP logs |
| /ecs/busyb-quickbooks-mcp | 7 | 3,268,552 | QuickBooks MCP logs |
| /ecs/busyb-research-mcp | 7 | 4,343,787 | Research MCP logs |
| /ecs/busyb-google-workspace-mcp | 30 | 0 | **Google Workspace MCP logs** ✓ |

### Google Workspace MCP Log Group Details
- **Log Group Name**: /ecs/busyb-google-workspace-mcp
- **Log Group ARN**: arn:aws:logs:us-east-1:758888582357:log-group:/ecs/busyb-google-workspace-mcp:*
- **Retention Policy**: 30 days
- **Created**: 2025-11-12
- **Tags**: Environment=production, Service=google-workspace-mcp, ManagedBy=ecs

---

## Database Infrastructure

### RDS (Aurora PostgreSQL)
- **DB Instance Identifier**: busyb-db-instance-1
- **Endpoint**: busyb-db-instance-1.co36sc0a8ry9.us-east-1.rds.amazonaws.com
- **Port**: 5432
- **Engine**: aurora-postgresql
- **Status**: available
- **Security Group**: sg-01cc83676f64d8b83

### ElastiCache (Redis)
- **Replication Group ID**: busyb-redis
- **Endpoint**: master.busyb-redis.vhxses.use1.cache.amazonaws.com
- **Port**: 6379
- **Status**: available
- **Security Group**: sg-014a1fede5eb05d8a

---

## Resources Needed for Google Workspace MCP

Based on this infrastructure inventory, the following resources need to be created:

### ✓ Already Exists
- VPC and subnets (reuse existing)
- Security groups (reuse busyb-ecs-sg and busyb-alb-sg)
- S3 bucket for OAuth tokens (busyb-oauth-tokens-758888582357)
- ECS cluster (busyb-cluster)
- ALB (busyb-alb)
- Google OAuth secrets (busyb/google-oauth-client-id, busyb/google-oauth-client-secret)

### ✓ Recently Created
1. **ECR Repository**: busyb-google-workspace-mcp (Created: 2025-11-12)
2. **CloudWatch Log Group**: /ecs/busyb-google-workspace-mcp (Created: 2025-11-12, 30-day retention)
3. **IAM Task Role**: busyb-google-workspace-mcp-task-role (Created: 2025-11-12, with S3 and Secrets Manager permissions)

### ✓ Phase 4 Created Resources

1. **ECS Task Definition**: busyb-google-workspace-mcp (Task 4.1 & 4.2 Complete)
   - **Task Definition ARN**: arn:aws:ecs:us-east-1:758888582357:task-definition/busyb-google-workspace-mcp:1
   - **Revision**: 1
   - **Status**: ACTIVE
   - **Registered**: 2025-11-12
   - **File Location**: `ecs/task-definition-google-workspace-mcp.json`
   - **Family**: busyb-google-workspace-mcp
   - **Network Mode**: awsvpc
   - **Launch Type**: FARGATE
   - **CPU**: 512 (0.5 vCPU)
   - **Memory**: 1024 MB
   - **Container Name**: busyb-google-workspace-mcp
   - **Container Port**: 8000
   - **Image**: 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest
   - **Health Check**: `curl -f http://localhost:8000/health || exit 1`
   - **Health Check Interval**: 30 seconds
   - **Health Check Timeout**: 5 seconds
   - **Health Check Retries**: 3
   - **Health Check Start Period**: 60 seconds
   - **Execution Role**: arn:aws:iam::758888582357:role/ecsTaskExecutionRole
   - **Task Role**: arn:aws:iam::758888582357:role/busyb-mcp-task-role
   - **Log Driver**: awslogs
   - **Log Group**: /ecs/busyb-google-workspace-mcp
   - **Log Stream Prefix**: ecs
   - **Environment Variables**:
     - PORT: 8000
     - WORKSPACE_MCP_PORT: 8000
     - WORKSPACE_MCP_BASE_URI: http://google-workspace.busyb.local
     - MCP_ENABLE_OAUTH21: true
     - MCP_SINGLE_USER_MODE: 0
     - OAUTHLIB_INSECURE_TRANSPORT: 0
   - **Secrets (from Secrets Manager)**:
     - MCP_GOOGLE_OAUTH_CLIENT_ID: arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id
     - MCP_GOOGLE_OAUTH_CLIENT_SECRET: arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret
     - MCP_GOOGLE_CREDENTIALS_DIR: arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket

2. **ALB Target Group**: busyb-google-workspace (Task 4.3 Complete)
   - **Target Group Name**: busyb-google-workspace
   - **Target Group ARN**: arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e
   - **Protocol**: HTTP
   - **Port**: 8000
   - **Target Type**: ip
   - **VPC**: vpc-0111b7630bcb61b61
   - **Health Check Configuration**:
     - Health Check Path: /health
     - Health Check Protocol: HTTP
     - Health Check Port: traffic-port
     - Health Check Interval: 30 seconds
     - Health Check Timeout: 5 seconds
     - Healthy Threshold: 2
     - Unhealthy Threshold: 3
     - Success Codes: 200
   - **Tags**:
     - Name: busyb-google-workspace
     - Service: google-workspace-mcp
     - Environment: production
   - **Created**: 2025-11-12

3. **ALB Listener Rule**: busyb-google-workspace routing (Task 4.4 Complete)
   - **Rule ARN**: arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4
   - **Listener ARN**: arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23
   - **Priority**: 50
   - **Path Pattern**: `/google-workspace/*`
   - **Action**: Forward to `busyb-google-workspace` target group
   - **Target Group**: arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e
   - **Created**: 2025-11-12

4. **AWS Cloud Map Service Discovery**: google-workspace.busyb.local (Task 4.5 Complete)
   - **Service Name**: google-workspace
   - **Service ID**: srv-gxethbb34gto3cbr
   - **Service ARN**: arn:aws:servicediscovery:us-east-1:758888582357:service/srv-gxethbb34gto3cbr
   - **Namespace**: busyb.local
   - **Namespace ID**: ns-vt3hun37drrxdy7p
   - **Namespace ARN**: arn:aws:servicediscovery:us-east-1:758888582357:namespace/ns-vt3hun37drrxdy7p
   - **DNS Name**: google-workspace.busyb.local
   - **Type**: DNS_HTTP
   - **Routing Policy**: MULTIVALUE
   - **DNS Records**:
     - Type A, TTL: 60 seconds
     - Type SRV, TTL: 60 seconds
   - **Health Check**: Custom (FailureThreshold=1)
   - **Description**: Service discovery for Google Workspace MCP
   - **Created**: 2025-11-12
   - **Purpose**: Allows Core Agent to reach Google Workspace MCP at `http://google-workspace.busyb.local:8000/mcp`

5. **ECS Service**: busyb-google-workspace-mcp-service (Task 4.6 Complete)
   - **Service Name**: busyb-google-workspace-mcp-service
   - **Service ARN**: arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-google-workspace-mcp-service
   - **Cluster**: busyb-cluster
   - **Task Definition**: busyb-google-workspace-mcp:3
   - **Launch Type**: FARGATE
   - **Platform Version**: LATEST
   - **Desired Count**: 1
   - **Status**: ACTIVE
   - **Network Configuration**:
     - **Subnets**: subnet-0ae07f54c7454fe72, subnet-0d2d334cbe1467f4b (private subnets)
     - **Security Groups**: sg-0ebf38ea0618aef2d (busyb-ecs-sg)
     - **Assign Public IP**: DISABLED
   - **Load Balancer Integration**:
     - **Target Group**: arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e
     - **Container**: busyb-google-workspace-mcp
     - **Container Port**: 8000
   - **Service Discovery Integration**:
     - **Registry ARN**: arn:aws:servicediscovery:us-east-1:758888582357:service/srv-gxethbb34gto3cbr
     - **DNS Name**: google-workspace.busyb.local
     - **Container**: busyb-google-workspace-mcp
     - **Container Port**: 8000
   - **ECS Exec**: Enabled
   - **Health Check Grace Period**: 60 seconds
   - **Deployment Configuration**:
     - **Maximum Percent**: 200
     - **Minimum Healthy Percent**: 100
   - **Created**: 2025-11-12

   **Docker Image**: 758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest
   - **Image Digest**: sha256:4fd85f2e637574dbb685a22584456a72ea5acc2c3898c6866b53bd69949a7f1a
   - **Pushed**: 2025-11-12

   **Operational Details**:
   - **Current Status**: ACTIVE and running (Task 4.7 - service verified healthy)
   - **Target Health**: HEALTHY (ALB target group health checks passing)
   - **Service Discovery**: Registered and accessible at `http://google-workspace.busyb.local:8000`
   - **External Access**: Configured via ALB with known path prefix issue (see Task 4.8 completion notes)

   **Service Configuration Summary**:
   - **Deployment Strategy**: Rolling update (max 200%, min 100% healthy)
   - **Health Check Grace Period**: 60 seconds
   - **Service Discovery DNS**: google-workspace.busyb.local (Port 8000)
   - **ALB Routing**: Path pattern `/google-workspace/*` → Target Group `busyb-google-workspace`
   - **ECS Exec**: Enabled (for debugging)
   - **Resource Allocation**: 0.5 vCPU, 1 GB memory per task
   - **Desired Task Count**: 1

   **Monitoring and Logging**:
   - **CloudWatch Log Group**: /ecs/busyb-google-workspace-mcp (30-day retention)
   - **Health Endpoint**: `/health` (HTTP 200 OK)
   - **Service Metrics**: CPU, Memory utilization tracked in CloudWatch
   - **ALB Metrics**: Request count, target response time, health checks

   **Documentation**:
   - Deployment guide: `docs/deployment.md` (updated with ECS details)
   - Operations runbook: `docs/operations.md` (created with operational procedures)
   - Task definition: `ecs/task-definition-google-workspace-mcp.json`

---

## Configuration Values for Deployment

Use these values when creating the Google Workspace MCP infrastructure:

```bash
# AWS Configuration
export AWS_REGION="us-east-1"
export AWS_ACCOUNT_ID="758888582357"

# VPC & Network
export VPC_ID="vpc-0111b7630bcb61b61"
export PRIVATE_SUBNET_1A="subnet-0d2d334cbe1467f4b"
export PRIVATE_SUBNET_1B="subnet-0ae07f54c7454fe72"
export PUBLIC_SUBNET_1A="subnet-07f1ff5451a4a7b86"
export PUBLIC_SUBNET_1B="subnet-0bfe170fb995b44b0"
export ECS_SECURITY_GROUP="sg-0ebf38ea0618aef2d"

# ECS Cluster
export ECS_CLUSTER="busyb-cluster"

# Load Balancer
export ALB_ARN="arn:aws:elasticloadbalancing:us-east-1:758888582357:loadbalancer/app/busyb-alb/5111c2db275a2af3"
export HTTPS_LISTENER_ARN="arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23"
export TARGET_GROUP_ARN="arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e"
export LISTENER_RULE_ARN="arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4"

# IAM Roles
export TASK_EXECUTION_ROLE_ARN="arn:aws:iam::758888582357:role/ecsTaskExecutionRole"
export TASK_ROLE_ARN="arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role"

# Service Discovery
export NAMESPACE_ID="ns-vt3hun37drrxdy7p"
export NAMESPACE_ARN="arn:aws:servicediscovery:us-east-1:758888582357:namespace/ns-vt3hun37drrxdy7p"
export SD_SERVICE_ARN="arn:aws:servicediscovery:us-east-1:758888582357:service/srv-gxethbb34gto3cbr"
export SD_SERVICE_ID="srv-gxethbb34gto3cbr"
export SD_DNS_NAME="google-workspace.busyb.local"

# S3 Bucket
export S3_CREDENTIALS_BUCKET="s3://busyb-oauth-tokens-758888582357"

# Secrets Manager
export GOOGLE_OAUTH_CLIENT_ID_SECRET_ARN="arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx"
export GOOGLE_OAUTH_CLIENT_SECRET_ARN="arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z"
export S3_CREDENTIALS_BUCKET_SECRET_ARN="arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM"

# Service Configuration
export SERVICE_NAME="busyb-google-workspace-mcp-service"
export TASK_FAMILY="busyb-google-workspace-mcp"
export CONTAINER_NAME="busyb-google-workspace-mcp"
export CONTAINER_PORT="8000"
export ECR_REPO_NAME="busyb-google-workspace-mcp"
export ECR_REPO_URI="758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp"
export LOG_GROUP_NAME="/ecs/busyb-google-workspace-mcp"
export LOG_GROUP_ARN="arn:aws:logs:us-east-1:758888582357:log-group:/ecs/busyb-google-workspace-mcp:*"
export ALB_PATH_PATTERN="/google-workspace/*"
```

---

## Infrastructure Compatibility Assessment

### ✓ Compatible & Ready
- **VPC & Networking**: Multi-AZ setup with public and private subnets is ideal for Fargate deployments
- **Security Groups**: Existing ECS security group allows ports 8000-8080, compatible with container port 8080
- **ALB**: Already configured with HTTPS, can add new routing rule
- **ECS Cluster**: Using Fargate, ready for new services
- **S3 Bucket**: Encrypted with KMS, suitable for storing OAuth tokens
- **Secrets Manager**: Google OAuth credentials already stored
- **IAM Roles**: ecsTaskExecutionRole has necessary permissions

### ⚠️ Considerations
1. **CloudWatch Log Retention**: Existing services use 7-day retention, plan specifies 30 days for Google Workspace MCP
2. **S3 Bucket Versioning**: Not enabled, consider enabling for credential history
3. **Task Role Pattern**: Need to follow existing pattern (separate task role per service) and add `s3:ListBucket` permission

### ✅ No Blocking Issues
All existing infrastructure is compatible with the Google Workspace MCP deployment requirements. The infrastructure follows AWS best practices with multi-AZ deployment, private subnets for ECS tasks, and secure credential management.

---

## AWS Credentials and Permissions Test Results

**Test Date**: 2025-11-12
**Test Phase**: Phase 1, Task 1.7
**Status**: ✅ **ALL TESTS PASSED**

### Test Summary

All AWS credentials and permissions have been verified and are working correctly. No permission issues were found.

| Resource | Test | Status | Details |
|----------|------|--------|---------|
| **ECR Repository** | Access to `busyb-google-workspace-mcp` | ✅ PASS | Repository accessible, metadata verified |
| **Secrets - Client ID** | Read `busyb/google-oauth-client-id` | ✅ PASS | JSON format verified, value retrieved |
| **Secrets - Client Secret** | Read `busyb/google-oauth-client-secret` | ✅ PASS | JSON format verified, value retrieved |
| **Secrets - S3 Bucket** | Read `busyb/s3-credentials-bucket` | ✅ PASS | Plain string format, value retrieved |
| **S3 Bucket - List** | List objects in `busyb-oauth-tokens-758888582357` | ✅ PASS | Bucket contents listed successfully |
| **S3 Bucket - Write** | Upload test file to bucket | ✅ PASS | Write permissions verified |
| **S3 Bucket - Delete** | Delete test file from bucket | ✅ PASS | Delete permissions verified |
| **CloudWatch Logs** | Access `/ecs/busyb-google-workspace-mcp` log group | ✅ PASS | Log group accessible, retention verified (30 days) |
| **ECS Cluster** | Access `busyb-cluster` | ✅ PASS | Cluster active, 5 services running |
| **IAM - Execution Role** | Verify `ecsTaskExecutionRole` | ✅ PASS | Role exists with correct policies attached |
| **IAM - Task Role** | Verify `busyb-google-workspace-mcp-task-role` | ✅ PASS | Role exists with correct inline policy |

### Key Findings

1. **All Permissions Working**: All required AWS permissions are correctly configured and functional.

2. **Secret Format Verified**: Google OAuth secrets are stored as JSON objects with keys:
   - `busyb/google-oauth-client-id`: `{"GOOGLE_OAUTH_CLIENT_ID": "359995978669-..."}`
   - `busyb/google-oauth-client-secret`: `{"GOOGLE_OAUTH_CLIENT_SECRET": "GOCSPX-..."}`
   - ECS task definition must use JSON key notation (see test results document)

3. **S3 Operations Verified**: All S3 operations required for OAuth credential storage are working:
   - List bucket contents
   - Read credential files
   - Write new credential files
   - Delete revoked credential files

4. **IAM Roles Verified**:
   - **ecsTaskExecutionRole**: Has `AmazonECSTaskExecutionRolePolicy` and `SecretsManagerReadWrite` policies
   - **busyb-google-workspace-mcp-task-role**: Has inline policy with S3 and Secrets Manager permissions
   - Both roles have correct trust relationships with `ecs-tasks.amazonaws.com`

5. **No Permission Issues**: Zero permission errors encountered during testing.

### Detailed Test Results

For complete test results, command outputs, and recommendations, see:
📄 **`plan_cicd/aws_credentials_test_results.md`**

### Test Validation Checklist

- [x] ECR repository accessible
- [x] Google OAuth Client ID secret readable
- [x] Google OAuth Client Secret secret readable
- [x] S3 credentials bucket secret readable
- [x] S3 bucket objects listable
- [x] S3 bucket write operations working
- [x] S3 bucket delete operations working
- [x] CloudWatch log group accessible
- [x] ECS cluster accessible
- [x] ECS Task Execution Role verified
- [x] Google Workspace MCP Task Role verified
- [x] IAM policies verified
- [x] No permission errors encountered

### Recommendations

1. **ECS Task Definition**: When creating task definition in Phase 4, use JSON key notation for secrets:
   ```
   valueFrom: "...secret-arn:GOOGLE_OAUTH_CLIENT_ID::"
   ```

2. **GitHub Actions**: Task 1.4 still requires manual creation of GitHub Actions IAM user and secrets.

3. **No Remediation Required**: All AWS resources and permissions are properly configured.

---

## Next Steps

✅ **Phase 1 Complete** - All prerequisites and AWS setup tasks finished
➡️ **Proceed to Phase 2** - Dockerfile Review & Optimization
