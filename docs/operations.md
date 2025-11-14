# Operations Guide

This guide provides operational procedures for managing the Google Workspace MCP Server running on AWS ECS.

## Table of Contents

- [Service Overview](#service-overview)
- [Viewing Service Status](#viewing-service-status)
- [Viewing Logs](#viewing-logs)
- [Scaling the Service](#scaling-the-service)
- [Updating the Service](#updating-the-service)
- [Rollback Procedures](#rollback-procedures)
- [Troubleshooting](#troubleshooting)
- [Incident Response](#incident-response)
- [Maintenance Procedures](#maintenance-procedures)

## Service Overview

### Service Configuration

- **Service Name**: `busyb-google-workspace-mcp-service`
- **Cluster**: `busyb-cluster`
- **Region**: `us-east-1`
- **Launch Type**: Fargate
- **Desired Count**: 1 task
- **Container Port**: 8000

### Key Resources

- **ECS Service ARN**: `arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-google-workspace-mcp-service`
- **Task Definition**: `busyb-google-workspace-mcp` (family)
- **Target Group ARN**: `arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e`
- **Service Discovery**: `google-workspace.busyb.local`
- **CloudWatch Log Group**: `/ecs/busyb-google-workspace-mcp`

### Access Points

**Internal Access** (Service Discovery):
```
http://google-workspace.busyb.local:8000
```

**External Access** (ALB):
```
https://busyb-alb-1791678277.us-east-1.elb.amazonaws.com/google-workspace/*
```
⚠️ Note: External access has path prefix issues. See [Troubleshooting](#troubleshooting-path-prefix-issue).

---

## Viewing Service Status

### Quick Status Check

View the service overview including running task count and recent events:

```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount,Events:events[0:5]}' \
  --output json \
  --region us-east-1
```

**Expected Output**:
```json
{
  "Status": "ACTIVE",
  "Running": 1,
  "Desired": 1,
  "Pending": 0,
  "Events": [
    {
      "message": "service busyb-google-workspace-mcp-service has reached a steady state."
    }
  ]
}
```

### Detailed Service Information

Get comprehensive service details:

```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1
```

Key fields to check:
- `status`: Should be "ACTIVE"
- `runningCount`: Should match `desiredCount`
- `deployments`: Shows active and pending deployments
- `events`: Recent service events (deployments, scaling, failures)

### Task Status

List all running tasks:

```bash
aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --region us-east-1
```

Get detailed task information:

```bash
# Get the first running task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING \
  --query 'taskArns[0]' \
  --output text \
  --region us-east-1)

# Get task details
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks ${TASK_ARN} \
  --query 'tasks[0].{TaskArn:taskArn,Status:lastStatus,Health:healthStatus,IP:attachments[0].details[?name==`privateIPv4Address`].value|[0],StartedAt:startedAt,CPU:cpu,Memory:memory}' \
  --output json \
  --region us-east-1
```

### Health Check Status

Check container health:

```bash
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks ${TASK_ARN} \
  --query 'tasks[0].containers[0].{Name:name,Health:healthStatus,Status:lastStatus,ExitCode:exitCode}' \
  --output json \
  --region us-east-1
```

**Health Status Values**:
- `HEALTHY`: Container passing health checks
- `UNHEALTHY`: Container failing health checks
- `UNKNOWN`: Health status not yet determined

### ALB Target Health

Check ALB target group health:

```bash
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e \
  --region us-east-1
```

**Expected Output**:
```json
{
  "TargetHealthDescriptions": [
    {
      "Target": {
        "Id": "10.0.10.254",
        "Port": 8000
      },
      "HealthCheckPort": "8000",
      "TargetHealth": {
        "State": "healthy"
      }
    }
  ]
}
```

**Target Health States**:
- `healthy`: Target is passing health checks
- `unhealthy`: Target is failing health checks
- `initial`: Target is being registered
- `draining`: Target is being deregistered

### Service Discovery Status

Check service discovery registration:

```bash
aws servicediscovery get-service \
  --id srv-gxethbb34gto3cbr \
  --region us-east-1
```

List registered instances:

```bash
aws servicediscovery list-instances \
  --service-id srv-gxethbb34gto3cbr \
  --region us-east-1
```

### CloudWatch Metrics

View CPU utilization (last 1 hour):

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average Maximum \
  --region us-east-1
```

View memory utilization:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average Maximum \
  --region us-east-1
```

---

## Viewing Logs

### Real-Time Log Streaming

Tail logs in real-time (follow mode):

```bash
aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1
```

**Tip**: Press Ctrl+C to stop following logs.

### Historical Logs

View logs from the last hour:

```bash
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --region us-east-1
```

View logs from the last 30 minutes:

```bash
aws logs tail /ecs/busyb-google-workspace-mcp --since 30m --region us-east-1
```

View logs from specific time:

```bash
aws logs tail /ecs/busyb-google-workspace-mcp --since 2025-11-12T10:00:00 --region us-east-1
```

### Filtered Logs

Filter logs by pattern (e.g., errors):

```bash
aws logs tail /ecs/busyb-google-workspace-mcp --follow --filter-pattern "ERROR" --region us-east-1
```

Filter for specific keywords:

```bash
# Search for OAuth-related logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --filter-pattern "OAuth" --region us-east-1

# Search for authentication failures
aws logs tail /ecs/busyb-google-workspace-mcp --since 1h --filter-pattern "Authentication" --region us-east-1

# Search for health check logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 5m --filter-pattern "/health" --region us-east-1
```

### Log Streams

List all log streams:

```bash
aws logs describe-log-streams \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --order-by LastEventTime \
  --descending \
  --max-items 10 \
  --region us-east-1
```

Get logs from specific stream:

```bash
LOG_STREAM="ecs/busyb-google-workspace-mcp/abc123def456"

aws logs get-log-events \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --log-stream-name ${LOG_STREAM} \
  --limit 100 \
  --region us-east-1
```

### CloudWatch Logs Insights

Run complex queries using CloudWatch Logs Insights:

```bash
# Query: Count errors by minute over the last hour
aws logs start-query \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | stats count() by bin(5m)' \
  --region us-east-1
```

Get query results (use query ID from previous command):

```bash
aws logs get-query-results --query-id <QUERY_ID> --region us-east-1
```

### Export Logs

Export logs to S3 for long-term storage or analysis:

```bash
aws logs create-export-task \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --from $(date -u -d '7 days ago' +%s)000 \
  --to $(date -u +%s)000 \
  --destination s3://your-log-archive-bucket \
  --destination-prefix google-workspace-mcp/logs/$(date +%Y/%m/%d) \
  --region us-east-1
```

---

## Scaling the Service

### Manual Scaling

Scale up to 2 tasks:

```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 2 \
  --region us-east-1
```

Scale down to 1 task:

```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 1 \
  --region us-east-1
```

### Monitor Scaling

Watch the service scale:

```bash
# Monitor service status
watch -n 5 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].{Desired:desiredCount,Running:runningCount,Pending:pendingCount}" \
  --output table \
  --region us-east-1'
```

### Auto Scaling Setup

Enable auto scaling based on CPU utilization:

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --min-capacity 1 \
  --max-capacity 4 \
  --region us-east-1

# Create CPU-based scaling policy
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --policy-name busyb-google-workspace-cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 60,
    "ScaleInCooldown": 180
  }' \
  --region us-east-1
```

View auto scaling policies:

```bash
aws application-autoscaling describe-scaling-policies \
  --service-namespace ecs \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --region us-east-1
```

Disable auto scaling:

```bash
# Delete scaling policy
aws application-autoscaling delete-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --policy-name busyb-google-workspace-cpu-scaling \
  --region us-east-1

# Deregister scalable target
aws application-autoscaling deregister-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/busyb-cluster/busyb-google-workspace-mcp-service \
  --region us-east-1
```

### Scaling Considerations

**When to scale up**:
- CPU utilization consistently above 70%
- Memory utilization consistently above 80%
- Request latency increasing
- Error rate increasing
- Expected traffic spike

**When to scale down**:
- CPU utilization consistently below 30%
- Memory utilization consistently below 40%
- Low traffic periods
- Cost optimization needed

**Scaling Limits**:
- Minimum: 1 task (for availability)
- Maximum: 4 tasks (or adjust based on needs)
- Each task: 0.5 vCPU, 1 GB memory

---

## Updating the Service

### Deploy New Image (Manual)

Force a new deployment to pull the latest `:latest` tag:

```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --force-new-deployment \
  --region us-east-1
```

Deploy specific image tag:

```bash
# Update task definition with new image
# Edit ecs/task-definition-google-workspace-mcp.json
# Change image tag from :latest to :abc123def

# Register new task definition revision
aws ecs register-task-definition \
  --cli-input-json file://ecs/task-definition-google-workspace-mcp.json \
  --region us-east-1

# Get new revision number
NEW_REVISION=$(aws ecs describe-task-definition \
  --task-definition busyb-google-workspace-mcp \
  --query 'taskDefinition.revision' \
  --output text \
  --region us-east-1)

# Update service to use new revision
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:${NEW_REVISION} \
  --region us-east-1
```

### Update Environment Variables

Edit the task definition JSON file:

```bash
# Edit ecs/task-definition-google-workspace-mcp.json
# Update environment variables in the "environment" section

# Register new revision
aws ecs register-task-definition \
  --cli-input-json file://ecs/task-definition-google-workspace-mcp.json \
  --region us-east-1

# Update service
NEW_REVISION=$(aws ecs describe-task-definition \
  --task-definition busyb-google-workspace-mcp \
  --query 'taskDefinition.revision' \
  --output text \
  --region us-east-1)

aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:${NEW_REVISION} \
  --force-new-deployment \
  --region us-east-1
```

### Update Resource Allocation

Change CPU/memory:

```bash
# Edit task definition JSON
# Update "cpu" and "memory" fields
# cpu: "256", "512", "1024", "2048", "4096"
# memory: Must be compatible with CPU (see AWS docs)

# Register and deploy new revision (same as above)
```

**Compatible CPU/Memory Combinations**:
- CPU 256: Memory 512, 1024, 2048
- CPU 512: Memory 1024-4096
- CPU 1024: Memory 2048-8192
- CPU 2048: Memory 4096-16384

### Monitor Deployment

Watch deployment progress:

```bash
# Monitor service events
watch -n 5 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].events[0:5]" \
  --output table \
  --region us-east-1'
```

Wait for deployment to stabilize:

```bash
aws ecs wait services-stable \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1

echo "Deployment complete!"
```

View deployment status:

```bash
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].deployments' \
  --output json \
  --region us-east-1
```

**Deployment States**:
- `PRIMARY`: Currently serving traffic
- `ACTIVE`: Being deployed (new version)
- `DRAINING`: Being replaced (old version)

### Deployment Behavior

**Zero-Downtime Deployment**:
1. New task starts (with new image/configuration)
2. New task passes health checks
3. New task is added to ALB target group
4. New task receives traffic
5. Old task is drained from target group
6. Old task stops receiving new requests
7. Old task completes existing requests
8. Old task is stopped

**Deployment Configuration**:
- **Maximum Percent**: 200% (allows 2 tasks during deployment)
- **Minimum Healthy Percent**: 100% (keeps at least 1 task running)

---

## Rollback Procedures

### Automatic Rollback

ECS automatically rolls back failed deployments if:
- New tasks fail to start
- New tasks fail health checks
- Deployment takes too long

**No manual action needed** - ECS will keep the old task running.

### Manual Rollback to Previous Revision

Identify the previous working revision:

```bash
# List recent task definition revisions
aws ecs list-task-definitions \
  --family-prefix busyb-google-workspace-mcp \
  --sort DESC \
  --max-items 5 \
  --region us-east-1
```

Rollback to specific revision:

```bash
# Rollback to revision 2
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:2 \
  --force-new-deployment \
  --region us-east-1
```

### Rollback Verification

Verify the rollback:

```bash
# Check service is using correct task definition
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].taskDefinition' \
  --output text \
  --region us-east-1

# Expected output: arn:aws:ecs:us-east-1:758888582357:task-definition/busyb-google-workspace-mcp:2

# Check tasks are running and healthy
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{Running:runningCount,Desired:desiredCount}' \
  --region us-east-1
```

### Emergency Rollback (Immediate)

If the service is in a critical state:

```bash
# 1. Stop all running tasks (forces immediate restart with new revision)
TASK_ARNS=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --query 'taskArns' \
  --output text \
  --region us-east-1)

for TASK_ARN in ${TASK_ARNS}; do
  aws ecs stop-task \
    --cluster busyb-cluster \
    --task ${TASK_ARN} \
    --reason "Emergency rollback" \
    --region us-east-1
done

# 2. Update service to previous revision
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp:2 \
  --force-new-deployment \
  --region us-east-1

# 3. Monitor new tasks
watch -n 2 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].{Running:runningCount,Desired:desiredCount}" \
  --region us-east-1'
```

### Rollback Checklist

After rollback:
- [ ] Verify service is running with correct task definition revision
- [ ] Verify running task count matches desired count
- [ ] Check task health status is HEALTHY
- [ ] Check ALB target health is healthy
- [ ] Test health endpoint: `curl http://google-workspace.busyb.local:8000/health`
- [ ] Review CloudWatch logs for errors
- [ ] Document the incident and root cause
- [ ] Plan fix for the issue that caused the rollback

---

## Troubleshooting

### Troubleshooting Path Prefix Issue

**Symptom**: External access via ALB returns 404 errors.

**Root Cause**: The application does not handle the `/google-workspace/` path prefix. Requests like `https://alb-dns/google-workspace/health` fail because the application expects `/health` directly.

**Verification**:
```bash
# This will fail (404)
curl -k https://busyb-alb-1791678277.us-east-1.elb.amazonaws.com/google-workspace/health

# This works (internal access, no prefix)
curl http://google-workspace.busyb.local:8000/health
```

**Resolution Options**:

**Option 1: Use Service Discovery (Recommended)**
- Core Agent already uses service discovery: `http://google-workspace.busyb.local:8000/mcp`
- No path prefix issues
- Lower latency (direct container communication)
- Already working correctly

**Option 2: Update ALB Listener Rule**
Change the path pattern to match other MCP services:
```bash
# Delete existing rule
aws elbv2 delete-rule \
  --rule-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4 \
  --region us-east-1

# Create new rule with /mcp/google-workspace* pattern
aws elbv2 create-rule \
  --listener-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23 \
  --priority 50 \
  --conditions Field=path-pattern,Values='/mcp/google-workspace*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e \
  --region us-east-1
```

**Option 3: Remove External ALB Access**
If external access is not needed, remove the listener rule:
```bash
aws elbv2 delete-rule \
  --rule-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4 \
  --region us-east-1
```

### Task Fails to Start

**Symptom**: Tasks start but immediately stop.

**Investigation**:
```bash
# Get stopped task ARN
STOPPED_TASK=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status STOPPED \
  --query 'taskArns[0]' \
  --output text \
  --region us-east-1)

# Get stopped reason
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks ${STOPPED_TASK} \
  --query 'tasks[0].{StoppedReason:stoppedReason,StoppedAt:stoppedAt,Containers:containers[0].{ExitCode:exitCode,Reason:reason}}' \
  --output json \
  --region us-east-1

# Check logs
aws logs tail /ecs/busyb-google-workspace-mcp --since 10m --region us-east-1
```

**Common Causes**:

1. **IAM Permission Errors**
   - Can't pull image from ECR
   - Can't access secrets from Secrets Manager
   - Can't access S3 bucket

   **Solution**: Verify IAM roles have correct permissions.

2. **Application Startup Errors**
   - Python import errors
   - Missing environment variables
   - Invalid OAuth credentials

   **Solution**: Check CloudWatch logs for error messages.

3. **Health Check Failures**
   - Application not listening on port 8000
   - Health endpoint returning errors

   **Solution**: Increase `startPeriod` in health check or fix application issues.

4. **Resource Constraints**
   - Out of memory
   - CPU throttling

   **Solution**: Increase task CPU/memory allocation.

### Health Checks Failing

**Symptom**: Tasks keep restarting, marked as UNHEALTHY.

**Investigation**:
```bash
# Check container health
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
  --query 'tasks[0].containers[0].{Health:healthStatus,LastStatus:lastStatus}' \
  --region us-east-1

# Test health endpoint from task
aws ecs execute-command \
  --cluster busyb-cluster \
  --task ${TASK_ARN} \
  --container busyb-google-workspace-mcp \
  --interactive \
  --command "curl -v http://localhost:8000/health" \
  --region us-east-1
```

**Common Causes**:

1. **Application Not Ready**
   - Still starting up
   - Dependencies not loaded

   **Solution**: Increase `startPeriod` to 90 seconds.

2. **Health Endpoint Error**
   - Database connection issues
   - Missing configuration

   **Solution**: Check application logs for errors.

3. **Port Misconfiguration**
   - Application listening on wrong port
   - Security group blocking traffic

   **Solution**: Verify PORT environment variable and security groups.

### Service Not Accessible

**Symptom**: Cannot reach service via service discovery or ALB.

**Investigation**:
```bash
# Check service discovery
aws servicediscovery list-instances \
  --service-id srv-gxethbb34gto3cbr \
  --region us-east-1

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e \
  --region us-east-1

# Test from within VPC (requires EC2 instance or ECS task)
# ssh into an EC2 instance in the same VPC
curl -v http://google-workspace.busyb.local:8000/health
```

**Common Causes**:

1. **Security Group Issues**
   - ECS security group not allowing traffic from ALB
   - Inter-service communication blocked

   **Solution**: Verify security group rules.

2. **Service Discovery Not Working**
   - DNS resolution failing
   - VPC DNS disabled

   **Solution**: Enable VPC DNS resolution and DNS hostnames.

3. **No Healthy Targets**
   - All tasks unhealthy
   - No tasks running

   **Solution**: Check task health and logs.

### OAuth/Authentication Errors

**Symptom**: Authentication failures, OAuth errors in logs.

**Investigation**:
```bash
# Check secrets in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id busyb/google-oauth-client-id \
  --query 'SecretString' \
  --output text \
  --region us-east-1

# Check S3 bucket access
aws s3 ls s3://busyb-oauth-tokens-758888582357/

# Check task role permissions
aws iam get-role-policy \
  --role-name busyb-google-workspace-mcp-task-role \
  --policy-name busyb-google-workspace-mcp-policy \
  --region us-east-1
```

**Common Causes**:

1. **Invalid OAuth Credentials**
   - Wrong client ID or secret
   - Credentials revoked

   **Solution**: Update secrets in Secrets Manager.

2. **S3 Access Denied**
   - IAM role missing permissions
   - Bucket policy blocking access

   **Solution**: Verify IAM role policy and S3 bucket policy.

3. **Credential Files Corrupted**
   - Invalid JSON in S3
   - Malformed credential data

   **Solution**: Delete corrupted credentials from S3 and reauthenticate.

### High CPU/Memory Usage

**Symptom**: Task using high CPU or memory, potential performance issues.

**Investigation**:
```bash
# Check task resource utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average Maximum \
  --region us-east-1
```

**Resolution**:

1. **Scale Up** (add more tasks):
   ```bash
   aws ecs update-service \
     --cluster busyb-cluster \
     --service busyb-google-workspace-mcp-service \
     --desired-count 2 \
     --region us-east-1
   ```

2. **Increase Resources** (bigger tasks):
   - Edit task definition
   - Increase CPU from 512 to 1024
   - Increase memory from 1024 to 2048
   - Deploy new revision

3. **Optimize Application**:
   - Review application logs for performance issues
   - Check for memory leaks
   - Optimize database queries
   - Add caching

### Log Errors and Stack Traces

**Common Error Patterns**:

**Error**: `ModuleNotFoundError`
- **Cause**: Missing Python dependencies
- **Solution**: Rebuild Docker image with correct requirements.txt

**Error**: `CannotPullContainerError`
- **Cause**: IAM execution role can't access ECR
- **Solution**: Verify execution role has `AmazonECSTaskExecutionRolePolicy`

**Error**: `AccessDeniedException` (Secrets Manager)
- **Cause**: Execution role can't read secrets
- **Solution**: Verify execution role has `secretsmanager:GetSecretValue` permission

**Error**: `NoCredentialsError` (S3)
- **Cause**: Task role missing S3 permissions
- **Solution**: Verify task role has S3 permissions

**Error**: `Health check failed`
- **Cause**: Application not responding to health checks
- **Solution**: Check application logs, increase start period

---

## Incident Response

### Incident Severity Levels

**Severity 1 (Critical)**: Service completely down
- All tasks stopped
- Cannot serve any traffic
- Core Agent cannot communicate with service

**Severity 2 (High)**: Service degraded
- Some tasks unhealthy
- Increased error rate
- Slow response times

**Severity 3 (Medium)**: Service impacted
- Individual tasks restarting
- Intermittent errors
- OAuth failures

**Severity 4 (Low)**: Monitoring alerts
- Resource usage high
- Non-critical errors in logs
- Slow trends

### Incident Response Checklist

**Immediate Actions** (0-5 minutes):
1. [ ] Assess severity level
2. [ ] Check service status: `aws ecs describe-services ...`
3. [ ] Check running task count
4. [ ] Check CloudWatch logs for errors
5. [ ] Notify team if Severity 1 or 2

**Investigation** (5-15 minutes):
1. [ ] Review recent deployments
2. [ ] Check CloudWatch metrics (CPU, memory, errors)
3. [ ] Check ALB target health
4. [ ] Review application logs
5. [ ] Test service endpoints

**Resolution** (15+ minutes):
1. [ ] Implement fix (rollback, scale up, configuration change)
2. [ ] Monitor service stabilization
3. [ ] Verify service health
4. [ ] Test critical functionality
5. [ ] Update incident status

**Post-Incident** (after resolution):
1. [ ] Document incident timeline
2. [ ] Identify root cause
3. [ ] Create action items for prevention
4. [ ] Update runbooks if needed
5. [ ] Conduct post-mortem if Severity 1-2

### Emergency Contacts

**AWS Support**: (if AWS infrastructure issue)
- Open support case: https://console.aws.amazon.com/support
- Severity based on business impact

**Google Workspace Support**: (if Google API issue)
- Support: https://workspace.google.com/support
- Status: https://www.google.com/appsstatus

---

## Maintenance Procedures

### Scheduled Maintenance

**Pre-Maintenance Checklist**:
1. [ ] Announce maintenance window to users
2. [ ] Review change plan
3. [ ] Create backup of task definition
4. [ ] Test changes in non-production environment
5. [ ] Prepare rollback plan

**During Maintenance**:
1. [ ] Make changes as planned
2. [ ] Monitor deployment/changes
3. [ ] Verify service health
4. [ ] Test critical functionality
5. [ ] Rollback if issues detected

**Post-Maintenance**:
1. [ ] Verify all functionality working
2. [ ] Monitor for 30 minutes
3. [ ] Update documentation
4. [ ] Announce completion to users
5. [ ] Document any issues encountered

### Routine Maintenance Tasks

**Daily**:
- Review CloudWatch alarms
- Check service health status
- Monitor error rates in logs

**Weekly**:
- Review CloudWatch metrics trends
- Check for new task definition revisions
- Review log retention and storage

**Monthly**:
- Review resource utilization and optimize
- Update dependencies (security patches)
- Review and rotate AWS credentials
- Check S3 bucket size and cleanup old tokens
- Review IAM policies and permissions

**Quarterly**:
- Review and update documentation
- Conduct disaster recovery drill
- Review cost optimization opportunities
- Update incident response runbooks

### Credential Rotation

**Rotate AWS Access Keys** (for GitHub Actions):
```bash
# Create new access key
aws iam create-access-key --user-name github-actions-google-workspace-mcp

# Update GitHub Secrets with new keys
# In GitHub: Settings → Secrets → Actions
# Update AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

# Test deployment with new keys

# Delete old access key (after verification)
aws iam delete-access-key \
  --user-name github-actions-google-workspace-mcp \
  --access-key-id <OLD_ACCESS_KEY_ID>
```

**Rotate Google OAuth Credentials**:
```bash
# Generate new credentials in Google Cloud Console

# Update secrets in Secrets Manager
aws secretsmanager update-secret \
  --secret-id busyb/google-oauth-client-id \
  --secret-string '{"GOOGLE_OAUTH_CLIENT_ID":"new-client-id"}' \
  --region us-east-1

aws secretsmanager update-secret \
  --secret-id busyb/google-oauth-client-secret \
  --secret-string '{"GOOGLE_OAUTH_CLIENT_SECRET":"new-client-secret"}' \
  --region us-east-1

# Force service redeployment to pick up new secrets
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --force-new-deployment \
  --region us-east-1

# All users will need to reauthenticate
```

### Log Retention Management

Review and adjust log retention:

```bash
# Check current retention
aws logs describe-log-groups \
  --log-group-name-prefix /ecs/busyb-google-workspace-mcp \
  --query 'logGroups[0].retentionInDays' \
  --region us-east-1

# Update retention (e.g., to 60 days)
aws logs put-retention-policy \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --retention-in-days 60 \
  --region us-east-1
```

### Cost Optimization

**Review Resource Usage**:
```bash
# Check average CPU usage over last 7 days
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster \
  --start-time $(date -u -d '7 days ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Average \
  --region us-east-1
```

If consistently low (<30%), consider:
- Reducing task CPU/memory allocation
- Using smaller instance size
- Consolidating with other services

**S3 Storage Cleanup**:
```bash
# List old OAuth tokens (if users haven't logged in for 90+ days)
aws s3 ls s3://busyb-oauth-tokens-758888582357/ --recursive

# Set lifecycle policy to delete old tokens
aws s3api put-bucket-lifecycle-configuration \
  --bucket busyb-oauth-tokens-758888582357 \
  --lifecycle-configuration file://s3-lifecycle-policy.json
```

---

## Additional Resources

- [Deployment Guide](./deployment.md) - Complete deployment documentation
- [Configuration Guide](./configuration.md) - Environment variables and settings
- [Authentication Guide](./authentication.md) - OAuth and credential management
- [Architecture Documentation](./architecture.md) - System design details

---

**Last Updated**: 2025-11-12 (Phase 4 CI/CD - Task 4.9)
