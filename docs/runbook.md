# Google Workspace MCP Production Runbook

## Table of Contents

1. [Service Overview](#service-overview)
2. [Service Endpoints](#service-endpoints)
3. [Architecture](#architecture)
4. [Deployment Procedures](#deployment-procedures)
5. [Monitoring and Observability](#monitoring-and-observability)
6. [Common Operations](#common-operations)
7. [Troubleshooting Guide](#troubleshooting-guide)
8. [Incident Response](#incident-response)
9. [Emergency Procedures](#emergency-procedures)
10. [Contact Information](#contact-information)

---

## Service Overview

### What is Google Workspace MCP?

The Google Workspace MCP (Model Context Protocol) Server provides AI assistants with secure, authenticated access to Google Workspace services including Gmail, Drive, Calendar, Docs, Sheets, and more.

### Key Features

- **OAuth 2.0 Authentication**: Secure user authentication via Google OAuth
- **Multi-User Support**: Isolated credentials per user stored in S3
- **MCP Protocol**: Standard Model Context Protocol for AI integrations
- **Comprehensive Tools**: 60+ tools across 9 Google Workspace services
- **Production-Ready**: Deployed on AWS ECS Fargate with automated CI/CD

### Service Characteristics

- **Language**: Python 3.12
- **Framework**: FastMCP (FastAPI-based)
- **Protocol**: JSON-RPC 2.0 over HTTP
- **Transport Mode**: streamable-http (SSE support)
- **Authentication**: OAuth 2.0 with PKCE
- **Credential Storage**: AWS S3 (encrypted)

---

## Service Endpoints

### Internal Service URL

**Primary**: `http://google-workspace.busyb.local:8000`

- **Access**: Within VPC only (service discovery)
- **Used by**: Core Agent, other internal services
- **DNS**: AWS Cloud Map service discovery

### External Access (if configured)

**ALB**: `https://<alb-dns>/google-workspace/`

- **Access**: Public (if ALB configured)
- **Used by**: Web clients, external integrations
- **Security**: ALB security groups, SSL termination

### Health Check

```bash
curl http://google-workspace.busyb.local:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "workspace-mcp",
  "version": "1.0.0",
  "transport": "streamable-http"
}
```

### MCP Endpoint

```bash
POST http://google-workspace.busyb.local:8000/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

---

## Architecture

### High-Level Architecture

```
┌─────────────┐
│ Core Agent  │
└──────┬──────┘
       │ HTTP
       │
       ▼
┌─────────────────────────────────┐
│   AWS Cloud Map (Service        │
│   Discovery)                    │
│   google-workspace.busyb.local  │
└────────────┬────────────────────┘
             │
             ▼
┌───────────────────────────────────┐
│  ECS Service                      │
│  busyb-google-workspace-mcp-      │
│  service                          │
│                                   │
│  ┌─────────────────────────────┐ │
│  │ Fargate Task                │ │
│  │ - CPU: 512 (0.5 vCPU)       │ │
│  │ - Memory: 1024 MB           │ │
│  │ - Port: 8000                │ │
│  └─────────────────────────────┘ │
└───────────────────────────────────┘
             │
             │ Uses
             ▼
┌─────────────────────────────────┐
│  S3 Bucket                      │
│  busyb-oauth-tokens             │
│  /google/{email}.json           │
│  - Server-side encryption       │
│  - Private access only          │
└─────────────────────────────────┘
             │
             │ Logs
             ▼
┌─────────────────────────────────┐
│  CloudWatch Logs                │
│  /ecs/busyb-google-workspace-   │
│  mcp                            │
└─────────────────────────────────┘
```

### AWS Resources

| Resource | Name | Purpose |
|----------|------|---------|
| **ECS Cluster** | busyb-cluster | Container orchestration |
| **ECS Service** | busyb-google-workspace-mcp-service | Service management |
| **Task Definition** | busyb-google-workspace-mcp | Container specification |
| **ECR Repository** | busyb-google-workspace-mcp | Docker images |
| **S3 Bucket** | busyb-oauth-tokens | OAuth credentials |
| **CloudWatch Log Group** | /ecs/busyb-google-workspace-mcp | Application logs |
| **IAM Task Role** | busyb-google-workspace-mcp-task-role | S3 access |
| **IAM Execution Role** | busyb-google-workspace-mcp-execution-role | ECR, CloudWatch access |
| **Service Discovery** | google-workspace.busyb.local | DNS for service |

### Network Architecture

- **VPC**: busyb-vpc
- **Subnets**: Private subnets (if configured)
- **Security Groups**: Allow inbound 8000 from VPC
- **Service Discovery**: AWS Cloud Map namespace `busyb.local`

---

## Deployment Procedures

### Automated Deployment (CI/CD)

**Trigger**: Push to `main` branch

**Process**:
1. GitHub Actions workflow triggers
2. Docker image built
3. Image pushed to ECR
4. New ECS task definition registered
5. ECS service updated
6. Old tasks drained, new tasks started
7. Health checks verify service

**Duration**: 8-13 minutes

**Monitor Deployment**:
```bash
# Watch GitHub Actions
gh run watch

# Monitor ECS service
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1
```

### Manual Deployment

**When to Use**: Emergency fixes, rollbacks, configuration changes

**Steps**:

1. **Build Docker Image**
   ```bash
   docker build -t busyb-google-workspace-mcp:manual .
   ```

2. **Tag Image**
   ```bash
   docker tag busyb-google-workspace-mcp:manual \
     590183811329.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:manual
   ```

3. **Push to ECR**
   ```bash
   aws ecr get-login-password --region us-east-1 | \
     docker login --username AWS --password-stdin \
     590183811329.dkr.ecr.us-east-1.amazonaws.com

   docker push 590183811329.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:manual
   ```

4. **Update Task Definition**
   ```bash
   # Download current task definition
   aws ecs describe-task-definition \
     --task-definition busyb-google-workspace-mcp \
     --query 'taskDefinition' > task-def.json

   # Edit task-def.json to update image tag

   # Register new task definition
   aws ecs register-task-definition --cli-input-json file://task-def.json
   ```

5. **Update Service**
   ```bash
   aws ecs update-service \
     --cluster busyb-cluster \
     --service busyb-google-workspace-mcp-service \
     --task-definition busyb-google-workspace-mcp \
     --force-new-deployment \
     --region us-east-1
   ```

6. **Wait for Stable**
   ```bash
   aws ecs wait services-stable \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1
   ```

### Rollback Procedure

**See**: [agent_notes/task_5.7-5.8_cicd_rollback_procedures.md](../agent_notes/task_5.7-5.8_cicd_rollback_procedures.md)

**Quick Rollback**:
```bash
# Get current revision
CURRENT=$(aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].taskDefinition' \
  --output text --region us-east-1 | grep -o '[0-9]*$')

# Rollback to previous
PREVIOUS=$((CURRENT - 1))

aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:${PREVIOUS} \
  --force-new-deployment \
  --region us-east-1
```

---

## Monitoring and Observability

### CloudWatch Logs

**Location**: `/ecs/busyb-google-workspace-mcp`

**View Recent Logs**:
```bash
aws logs tail /ecs/busyb-google-workspace-mcp \
  --since 1h \
  --region us-east-1
```

**Follow Logs (Live)**:
```bash
aws logs tail /ecs/busyb-google-workspace-mcp \
  --follow \
  --region us-east-1
```

**Filter Errors**:
```bash
aws logs tail /ecs/busyb-google-workspace-mcp \
  --since 1h \
  --filter-pattern "ERROR" \
  --region us-east-1
```

### CloudWatch Insights Queries

**Find All Errors in Last Hour**:
```
fields @timestamp, @message
| filter @message like /ERROR/
| sort @timestamp desc
| limit 100
```

**OAuth Success Rate**:
```
fields @timestamp, @message
| filter @message like /OAuth/
| stats count(@message like /success/) as successes,
        count(@message like /failed/) as failures
| extend total = successes + failures
| extend success_rate = successes * 100 / total
```

**Request Rate by Tool**:
```
fields @timestamp, @message
| filter @message like /tools\/call/
| parse @message "tool=*" as tool
| stats count() by tool
| sort count() desc
```

**Response Time Distribution**:
```
fields @timestamp, @message
| filter @message like /duration/
| parse @message "duration=*ms" as duration
| stats avg(duration), percentile(duration, 50), percentile(duration, 95), percentile(duration, 99)
```

### ECS Service Metrics

**View Service Status**:
```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].[serviceName,status,runningCount,desiredCount,pendingCount]' \
  --output table \
  --region us-east-1
```

**View Recent Events**:
```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].events[0:10]' \
  --region us-east-1
```

**View Task Status**:
```bash
aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --region us-east-1
```

**View Task Details**:
```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text \
  --region us-east-1)

aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks $TASK_ARN \
  --region us-east-1
```

### Health Check

**Manual Health Check**:
```bash
curl -f http://google-workspace.busyb.local:8000/health
```

**From Core Agent Container**:
```bash
# Execute command in Core Agent container
aws ecs execute-command \
  --cluster busyb-cluster \
  --task <TASK_ARN> \
  --container core-agent \
  --interactive \
  --command "/bin/bash" \
  --region us-east-1

# Inside container:
curl http://google-workspace.busyb.local:8000/health
```

---

## Common Operations

### View Service Status

```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1
```

### View Logs

```bash
# Recent logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --region us-east-1

# Live logs
aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1

# Error logs only
aws logs tail /ecs/busyb-google-workspace-mcp --follow --filter-pattern "ERROR" --region us-east-1
```

### Scale Service

**Increase Task Count**:
```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 2 \
  --region us-east-1
```

**Decrease Task Count**:
```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 1 \
  --region us-east-1
```

### Restart Service

**Force New Deployment** (rolling restart):
```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --force-new-deployment \
  --region us-east-1

# Wait for completion
aws ecs wait services-stable \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1
```

### Update Environment Variables

```bash
# 1. Download current task definition
aws ecs describe-task-definition \
  --task-definition busyb-google-workspace-mcp \
  --query 'taskDefinition' > task-def.json

# 2. Edit task-def.json to modify environment variables
# Remove these fields: taskDefinitionArn, revision, status, requiresAttributes, compatibilities, registeredAt, registeredBy

# 3. Register new task definition
aws ecs register-task-definition --cli-input-json file://task-def.json

# 4. Update service
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp \
  --force-new-deployment \
  --region us-east-1
```

### View S3 Credentials

```bash
# List credential files
aws s3 ls s3://busyb-oauth-tokens/google/

# View specific credential
aws s3 cp s3://busyb-oauth-tokens/google/user@gmail.com.json - | python3 -m json.tool
```

### Delete User Credentials

```bash
# Delete credential file
aws s3 rm s3://busyb-oauth-tokens/google/user@gmail.com.json

# User will need to re-authenticate
```

### View Task Definition Revisions

```bash
# List all revisions
aws ecs list-task-definitions \
  --family-prefix busyb-google-workspace-mcp \
  --sort DESC \
  --region us-east-1

# View specific revision
aws ecs describe-task-definition \
  --task-definition busyb-google-workspace-mcp:5 \
  --region us-east-1
```

### Connect to Running Task

**Note**: Requires ECS Exec enabled on task definition

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text \
  --region us-east-1)

# Connect to task
aws ecs execute-command \
  --cluster busyb-cluster \
  --task $TASK_ARN \
  --container workspace-mcp \
  --interactive \
  --command "/bin/bash" \
  --region us-east-1
```

---

## Troubleshooting Guide

### Service Won't Start

**Symptoms**:
- Tasks starting but immediately stopping
- Service never reaches stable state
- Tasks in PENDING state indefinitely

**Diagnostic Steps**:

1. **Check Task Status**
   ```bash
   aws ecs describe-tasks \
     --cluster busyb-cluster \
     --tasks $(aws ecs list-tasks --cluster busyb-cluster --service-name busyb-google-workspace-mcp-service --query 'taskArns[0]' --output text) \
     --region us-east-1
   ```

2. **Check CloudWatch Logs**
   ```bash
   aws logs tail /ecs/busyb-google-workspace-mcp --since 10m --region us-east-1
   ```

3. **Check Task Definition**
   ```bash
   aws ecs describe-task-definition \
     --task-definition busyb-google-workspace-mcp \
     --region us-east-1
   ```

**Common Causes**:
- **Missing environment variables**: Check GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET
- **Invalid Docker image**: Check ECR repository has image
- **Insufficient resources**: Check CPU/memory limits
- **Port conflicts**: Check port 8000 is available
- **Network issues**: Check security groups, VPC configuration

**Resolution**:
```bash
# Verify environment variables
aws ecs describe-task-definition \
  --task-definition busyb-google-workspace-mcp \
  --query 'taskDefinition.containerDefinitions[0].environment' \
  --region us-east-1

# Check if image exists in ECR
aws ecr describe-images \
  --repository-name busyb-google-workspace-mcp \
  --region us-east-1

# Rollback to previous version if needed
# (See Rollback Procedure above)
```

---

### Health Checks Failing

**Symptoms**:
- Tasks starting but marked unhealthy
- Service cycling tasks continuously
- 503 errors from service

**Diagnostic Steps**:

1. **Test Health Endpoint Manually**
   ```bash
   curl -v http://google-workspace.busyb.local:8000/health
   ```

2. **Check Application Logs**
   ```bash
   aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1
   ```

3. **Check Task Health Status**
   ```bash
   aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query 'services[0].events[0:5]' \
     --region us-east-1
   ```

**Common Causes**:
- Application startup error
- Port binding failure
- Database/S3 connectivity issues
- Invalid configuration

**Resolution**:
- Check logs for startup errors
- Verify environment variables
- Test S3 bucket access
- Rollback if necessary

---

### OAuth Authentication Errors

**Symptoms**:
- Users unable to authenticate
- "Invalid grant" errors
- Credentials not stored in S3

**Diagnostic Steps**:

1. **Check OAuth Configuration**
   ```bash
   # Verify environment variables
   aws ecs describe-task-definition \
     --task-definition busyb-google-workspace-mcp \
     --query 'taskDefinition.containerDefinitions[0].environment' \
     --region us-east-1 | grep GOOGLE_OAUTH
   ```

2. **Test OAuth Flow**
   ```bash
   # Try authentication
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "start_google_auth",
         "arguments": {
           "service_name": "gmail",
           "user_google_email": "test@gmail.com"
         }
       }
     }'
   ```

3. **Check CloudWatch Logs for OAuth Errors**
   ```bash
   aws logs tail /ecs/busyb-google-workspace-mcp \
     --since 1h \
     --filter-pattern "OAuth" \
     --region us-east-1
   ```

**Common Causes**:
- Invalid OAuth client credentials
- Redirect URI mismatch
- Expired or revoked refresh tokens
- S3 permission issues

**Resolution**:
- Verify OAuth credentials in Google Cloud Console
- Check redirect URI matches configuration
- Delete and recreate credentials for user
- Verify IAM role has S3 access

---

### S3 Access Errors

**Symptoms**:
- "Access Denied" errors in logs
- Credentials not saving/loading
- "NoSuchBucket" errors

**Diagnostic Steps**:

1. **Check S3 Bucket Exists**
   ```bash
   aws s3 ls s3://busyb-oauth-tokens/google/
   ```

2. **Check IAM Task Role Permissions**
   ```bash
   aws iam get-role-policy \
     --role-name busyb-google-workspace-mcp-task-role \
     --policy-name S3Access
   ```

3. **Test S3 Access from Task**
   ```bash
   # Connect to task
   aws ecs execute-command \
     --cluster busyb-cluster \
     --task <TASK_ARN> \
     --container workspace-mcp \
     --interactive \
     --command "/bin/bash"

   # Inside container:
   aws s3 ls s3://busyb-oauth-tokens/google/
   ```

**Common Causes**:
- IAM role missing S3 permissions
- S3 bucket doesn't exist
- Bucket name typo in environment variable
- Bucket in wrong region

**Resolution**:
- Update IAM policy with S3 permissions
- Create S3 bucket if missing
- Verify GOOGLE_MCP_CREDENTIALS_DIR environment variable
- Check bucket region matches configuration

---

### High CPU/Memory Usage

**Symptoms**:
- Service slow to respond
- Task killed due to OOM
- CPU throttling

**Diagnostic Steps**:

1. **Check Current Usage**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name CPUUtilization \
     --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
     --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average Maximum \
     --region us-east-1
   ```

2. **Check Memory Usage**
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name MemoryUtilization \
     --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
     --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 300 \
     --statistics Average Maximum \
     --region us-east-1
   ```

3. **Check Task Count vs Load**
   ```bash
   aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1
   ```

**Common Causes**:
- High request volume
- Insufficient task count
- Memory leak
- Inefficient code

**Resolution**:
- Scale up task count
- Increase CPU/memory allocation
- Implement auto-scaling
- Optimize application code

---

### Slow Response Times

**Symptoms**:
- Requests taking > 5 seconds
- Timeouts
- User complaints about performance

**Diagnostic Steps**:

1. **Test Response Time**
   ```bash
   time curl http://google-workspace.busyb.local:8000/health
   ```

2. **Check CloudWatch Logs for Slow Requests**
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/busyb-google-workspace-mcp \
     --filter-pattern "[timestamp, request_id, level, msg, duration > 5000]" \
     --region us-east-1
   ```

3. **Check Service Load**
   ```bash
   # Check CPU/memory
   # (See High CPU/Memory Usage above)
   ```

**Common Causes**:
- Google API rate limits
- High service load
- Network latency
- S3 latency (credentials loading)

**Resolution**:
- Implement caching
- Scale service horizontally
- Optimize API calls
- Use S3 Transfer Acceleration

---

## Incident Response

### Incident Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **Critical** | Service completely down, all users affected | < 15 min | Immediate |
| **High** | Major feature broken, significant user impact | < 1 hour | Page on-call |
| **Medium** | Degraded performance, some users affected | < 4 hours | Notify team |
| **Low** | Minor issues, few users affected | < 24 hours | Regular workflow |

### Incident Response Process

#### 1. Detection

**Automatic**:
- CloudWatch alarms (future)
- Health check failures
- User reports

**Manual**:
- Monitoring dashboard
- Log analysis
- Testing

#### 2. Assessment

```bash
# Quick assessment checklist

# 1. Is service running?
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1

# 2. Are tasks healthy?
aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --region us-east-1

# 3. Health check passing?
curl http://google-workspace.busyb.local:8000/health

# 4. Recent errors?
aws logs tail /ecs/busyb-google-workspace-mcp \
  --since 10m \
  --filter-pattern "ERROR" \
  --region us-east-1

# 5. Recent deployments?
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].events[0:3]' \
  --region us-east-1
```

#### 3. Communication

- Notify stakeholders
- Create incident ticket
- Update status page (if applicable)
- Document incident timeline

#### 4. Mitigation

**Immediate Actions**:
- Rollback if recent deployment caused issue
- Scale up if capacity issue
- Restart service if transient error

**Example Rollback**:
```bash
# See Rollback Procedure section above
```

#### 5. Resolution

- Fix root cause
- Test fix
- Deploy fix
- Verify resolution
- Update status

#### 6. Post-Mortem

- Document incident
- Identify root cause
- Create action items
- Improve monitoring/alerting
- Update runbook

### Common Incident Scenarios

#### Scenario 1: Service Completely Down

**Symptoms**: All requests fail, health checks failing

**Immediate Actions**:
1. Check if task is running
2. Check recent deployments
3. Review CloudWatch logs
4. Rollback if recent deployment
5. Restart service if transient

**Commands**:
```bash
# Check status
aws ecs describe-services --cluster busyb-cluster --services busyb-google-workspace-mcp-service --region us-east-1

# Rollback
# (See Rollback Procedure)

# Or restart
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --force-new-deployment --region us-east-1
```

#### Scenario 2: Intermittent Errors

**Symptoms**: Some requests succeed, some fail

**Immediate Actions**:
1. Check CloudWatch logs for errors
2. Check resource utilization
3. Scale up if needed
4. Check Google API status

**Commands**:
```bash
# Check error rate
aws logs tail /ecs/busyb-google-workspace-mcp --since 10m --filter-pattern "ERROR" --region us-east-1

# Scale up
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --desired-count 2 --region us-east-1
```

#### Scenario 3: Performance Degradation

**Symptoms**: Service slow but functional

**Immediate Actions**:
1. Check CPU/memory usage
2. Check request volume
3. Scale horizontally if needed
4. Implement rate limiting if abuse

**Commands**:
```bash
# Check metrics
# (See Monitoring section)

# Scale
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --desired-count 2 --region us-east-1
```

---

## Emergency Procedures

### Emergency Contacts

| Role | Name | Contact | Hours |
|------|------|---------|-------|
| Primary On-Call | TBD | TBD | 24/7 |
| Secondary On-Call | TBD | TBD | 24/7 |
| Engineering Manager | TBD | TBD | Business hours |
| DevOps Lead | TBD | TBD | Business hours |

### Emergency Rollback

**When**: Critical production issue, need to restore service immediately

**How**: See [Task 5.8 Rollback Procedures](../agent_notes/task_5.7-5.8_cicd_rollback_procedures.md)

**Quick Command**:
```bash
./rollback.sh  # If rollback script exists
```

### Emergency Service Stop

**When**: Security incident, data breach, need to stop all access

```bash
# Stop service immediately (scale to 0)
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 0 \
  --region us-east-1

# Notify stakeholders
# Investigate incident
# Document findings
```

### Emergency Credential Revocation

**When**: Credentials compromised, need to revoke all access

```bash
# Delete all credentials from S3
aws s3 rm s3://busyb-oauth-tokens/google/ --recursive

# Restart service
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --force-new-deployment \
  --region us-east-1

# Users will need to re-authenticate
```

---

## Contact Information

### Team Contacts

- **Engineering Team**: TBD
- **DevOps Team**: TBD
- **Security Team**: TBD

### External Contacts

- **Google Cloud Support**: https://cloud.google.com/support
- **AWS Support**: https://console.aws.amazon.com/support/
- **GitHub Support**: https://support.github.com/

### Related Documentation

- **Architecture Documentation**: [docs/architecture.md](./architecture.md)
- **Development Guide**: [docs/development.md](./development.md)
- **Authentication Guide**: [docs/authentication.md](./authentication.md)
- **Configuration Guide**: [docs/configuration.md](./configuration.md)
- **CI/CD Phase Plans**: [plan_cicd/](../plan_cicd/)
- **Agent Notes**: [agent_notes/](../agent_notes/)
- **Monitoring Plan**: [docs/monitoring-plan.md](./monitoring-plan.md)

---

## Appendix

### Useful AWS CLI Aliases

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# ECS aliases
alias ecs-status='aws ecs describe-services --cluster busyb-cluster --services busyb-google-workspace-mcp-service --region us-east-1'
alias ecs-logs='aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1'
alias ecs-tasks='aws ecs list-tasks --cluster busyb-cluster --service-name busyb-google-workspace-mcp-service --region us-east-1'
alias ecs-restart='aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --force-new-deployment --region us-east-1'

# S3 aliases
alias s3-creds='aws s3 ls s3://busyb-oauth-tokens/google/'
```

### Quick Reference Commands

```bash
# Service status
aws ecs describe-services --cluster busyb-cluster --services busyb-google-workspace-mcp-service --region us-east-1

# View logs
aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1

# Scale service
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --desired-count 2 --region us-east-1

# Force restart
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --force-new-deployment --region us-east-1

# Rollback
# Get current revision, subtract 1, then:
aws ecs update-service --cluster busyb-cluster --service busyb-google-workspace-mcp-service --task-definition busyb-google-workspace-mcp:N --force-new-deployment --region us-east-1

# Health check
curl http://google-workspace.busyb.local:8000/health
```

---

**Last Updated**: 2025-01-12
**Document Version**: 1.0
**Next Review**: 2025-02-12
