# Manual Actions Required - Google Workspace MCP Deployment

**Project**: Google Workspace MCP Server
**Date**: 2025-11-12
**Status**: Infrastructure deployed, awaiting manual configuration

---

## 🔴 CRITICAL - Required Before Production Use

### 1. Verify Google OAuth Credentials in AWS Secrets Manager

**Why**: The application needs valid Google OAuth credentials to authenticate users.

**Action Required**:
```bash
# Check if secrets exist and have correct values
aws secretsmanager get-secret-value \
  --secret-id busyb/google-oauth-client-id \
  --region us-east-1 \
  --query 'SecretString' \
  --output text

aws secretsmanager get-secret-value \
  --secret-id busyb/google-oauth-client-secret \
  --region us-east-1 \
  --query 'SecretString' \
  --output text
```

**What to Verify**:
- ✅ Secrets exist in AWS Secrets Manager
- ✅ Client ID format: `xxxxx.apps.googleusercontent.com`
- ✅ Client Secret is not empty
- ✅ Credentials are from Google Cloud Console OAuth 2.0 client

**If Missing or Incorrect**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to: APIs & Services → Credentials
3. Create or locate OAuth 2.0 Client ID (type: Web application)
4. Add authorized redirect URI: `http://localhost:8000/oauth2callback`
5. Update secrets in AWS:
```bash
# Update client ID
aws secretsmanager put-secret-value \
  --secret-id busyb/google-oauth-client-id \
  --secret-string "YOUR-CLIENT-ID.apps.googleusercontent.com" \
  --region us-east-1

# Update client secret
aws secretsmanager put-secret-value \
  --secret-id busyb/google-oauth-client-secret \
  --secret-string "YOUR-CLIENT-SECRET" \
  --region us-east-1
```

6. Force new ECS deployment to pick up updated secrets:
```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --force-new-deployment \
  --region us-east-1
```

**Documentation**: See `docs/configuration.md` section "OAuth Configuration"

---

### 2. Verify S3 Credential Storage Configuration

**Why**: User OAuth tokens need to be stored in S3 for persistence.

**Action Required**:
```bash
# Check S3 credentials directory secret
aws secretsmanager get-secret-value \
  --secret-id busyb/s3-credentials-bucket \
  --region us-east-1 \
  --query 'SecretString' \
  --output text
```

**Expected Value**: `s3://busyb-oauth-tokens-758888582357/`

**Verify S3 Bucket**:
```bash
# Check bucket exists and is accessible
aws s3 ls s3://busyb-oauth-tokens-758888582357/

# Check bucket encryption
aws s3api get-bucket-encryption \
  --bucket busyb-oauth-tokens-758888582357
```

**If Missing or Incorrect**:
1. Verify bucket name in AWS S3 console
2. Update secret with correct S3 path:
```bash
aws secretsmanager put-secret-value \
  --secret-id busyb/s3-credentials-bucket \
  --secret-string "s3://busyb-oauth-tokens-758888582357/" \
  --region us-east-1
```

3. Ensure task role has S3 permissions (should already be configured):
   - Role: `busyb-google-workspace-mcp-task-role`
   - Permissions: GetObject, PutObject, DeleteObject, ListBucket

**Documentation**: See `docs/configuration.md` section "S3 Credential Storage"

---

### 3. Execute OAuth Authentication Testing

**Why**: Verify the complete OAuth flow works before production use.

**Action Required**:
1. **Follow test procedure**: See `agent_notes/task_5.2_oauth_test_procedure.md`
2. **Use a test Google account** (not production user data)
3. **Estimated time**: 1-2 hours for complete testing

**Key Test Cases** (6 scenarios):
- ✅ Test Case 1: New user authentication flow
- ✅ Test Case 2: Token refresh validation
- ✅ Test Case 3: Multi-user session management
- ✅ Test Case 4: S3 credential storage verification
- ✅ Test Case 5: Session isolation testing
- ✅ Test Case 6: Error handling verification

**How to Test**:
```bash
# Monitor logs during testing
aws logs tail /ecs/busyb-google-workspace-mcp \
  --follow \
  --region us-east-1

# Verify credentials stored in S3 after auth
aws s3 ls s3://busyb-oauth-tokens-758888582357/
```

**Documentation**: Complete procedures in `agent_notes/task_5.2_oauth_test_procedure.md`

---

### 4. Test Critical Google Workspace Tools

**Why**: Ensure core functionality works with Google APIs.

**Action Required**:
1. **Follow test procedures**: See `agent_notes/task_5.3-5.6_tools_test_procedures.md`
2. **Test at minimum**: Gmail, Drive, Calendar (most critical)
3. **Estimated time**: 2-4 hours for critical tools

**Critical Tools to Test**:

**Gmail** (13 tools):
- Search messages
- Get message details
- Send email
- List labels

**Drive** (13 tools):
- List files
- Upload file
- Download file
- Share file

**Calendar** (10 tools):
- List events
- Create event
- Update event
- Delete event

**Testing Method**:
The test document provides MCP JSON-RPC examples for each tool. You can test via:
1. Core Agent (production method)
2. Direct curl commands to MCP endpoint
3. Automated test script (provided in test procedures)

**Documentation**: Complete procedures in `agent_notes/task_5.3-5.6_tools_test_procedures.md`

---

## 🟡 IMPORTANT - Recommended Before Production

### 5. Configure Basic CloudWatch Alarms

**Why**: Get alerted if the service has issues.

**Action Required**:
```bash
# Create alarm for unhealthy tasks
aws cloudwatch put-metric-alarm \
  --alarm-name busyb-google-workspace-mcp-unhealthy-tasks \
  --alarm-description "Alert when no healthy tasks running" \
  --metric-name HealthyTaskCount \
  --namespace AWS/ECS \
  --statistic Average \
  --period 60 \
  --evaluation-periods 2 \
  --threshold 1 \
  --comparison-operator LessThanThreshold \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster

# Create alarm for high CPU
aws cloudwatch put-metric-alarm \
  --alarm-name busyb-google-workspace-mcp-high-cpu \
  --alarm-description "Alert when CPU usage is high" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster

# Create alarm for high memory
aws cloudwatch put-metric-alarm \
  --alarm-name busyb-google-workspace-mcp-high-memory \
  --alarm-description "Alert when memory usage is high" \
  --metric-name MemoryUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=busyb-google-workspace-mcp-service Name=ClusterName,Value=busyb-cluster
```

**Configure SNS for Alerts**:
```bash
# Create SNS topic for alerts
aws sns create-topic --name busyb-google-workspace-mcp-alerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:758888582357:busyb-google-workspace-mcp-alerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Update alarms to send to SNS (example for one alarm)
aws cloudwatch put-metric-alarm \
  --alarm-name busyb-google-workspace-mcp-unhealthy-tasks \
  --alarm-actions arn:aws:sns:us-east-1:758888582357:busyb-google-workspace-mcp-alerts \
  # ... other parameters same as above
```

**Documentation**: See `docs/monitoring-plan.md` for complete alarm configurations

---

### 6. Scale to 2 Tasks for Redundancy

**Why**: Ensures high availability if one task fails.

**Action Required**:
```bash
# Scale service to 2 tasks
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --desired-count 2 \
  --region us-east-1

# Wait for service to stabilize
aws ecs wait services-stable \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1

# Verify both tasks are healthy
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{Running:runningCount,Desired:desiredCount}' \
  --region us-east-1
```

**When to Do**: After initial OAuth and tools testing is complete (Week 1)

**Cost Impact**: ~$18/month → ~$36/month (additional task)

**Documentation**: See `docs/operations.md` section "Scaling Procedures"

---

### 7. Test Rollback Procedure

**Why**: Ensure you can quickly recover from a bad deployment.

**Action Required**:
1. **Follow rollback procedures**: See `agent_notes/task_5.7-5.8_cicd_rollback_procedures.md`
2. **Test rollback script**: Script provided for <5 minute recovery
3. **Estimated time**: 30-45 minutes

**Quick Rollback Script** (provided in documentation):
```bash
#!/bin/bash
# Quick rollback to previous task definition revision

CLUSTER="busyb-cluster"
SERVICE="busyb-google-workspace-mcp-service"
REGION="us-east-1"

# Get current task definition
CURRENT_TASK_DEF=$(aws ecs describe-services \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION \
  --query 'services[0].taskDefinition' \
  --output text)

echo "Current task definition: $CURRENT_TASK_DEF"

# Extract revision number and calculate previous
CURRENT_REVISION=$(echo $CURRENT_TASK_DEF | grep -o '[0-9]*$')
PREVIOUS_REVISION=$((CURRENT_REVISION - 1))

echo "Rolling back from revision $CURRENT_REVISION to $PREVIOUS_REVISION"

# Perform rollback
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --task-definition busyb-google-workspace-mcp:$PREVIOUS_REVISION \
  --force-new-deployment \
  --region $REGION

echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION

echo "✅ Rollback complete!"
```

**Documentation**: Complete procedures in `agent_notes/task_5.7-5.8_cicd_rollback_procedures.md`

---

### 8. Execute Performance Baseline Testing

**Why**: Establish performance metrics and identify capacity limits.

**Action Required**:
1. **Follow performance testing guide**: See `agent_notes/task_5.9_performance_testing.md`
2. **Install k6**: `brew install k6` (macOS) or `apt-get install k6` (Linux)
3. **Run test suite**: 5 test scripts provided
4. **Estimated time**: 1-2 hours

**Test Scripts Provided**:
1. Health endpoint baseline
2. OAuth operations load test
3. Gmail API operations test
4. Concurrent users simulation
5. Stress test (finding limits)

**Example Test Execution**:
```bash
# Run health endpoint baseline
k6 run health-endpoint-baseline.js

# Monitor during test
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{CPU:cpuUtilization,Memory:memoryUtilization}'
```

**Documentation**: Complete test suite in `agent_notes/task_5.9_performance_testing.md`

---

## 🔵 OPTIONAL - Nice to Have

### 9. Fix ALB Path Prefix Issue (If External Access Needed)

**Why**: Currently external ALB access returns 404 due to path prefix mismatch.

**Status**: ⚠️ **NON-BLOCKING** - Core Agent uses service discovery (works fine)

**When Needed**: Only if you need external browser access to the service

**Action Options** (choose one):

**Option 1: Update ALB Listener Rule** (Simplest)
```bash
# Get listener ARN
LISTENER_ARN="arn:aws:elasticloadbalancing:us-east-1:758888582357:listener/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23"

# Delete existing rule
aws elbv2 delete-rule \
  --rule-arn arn:aws:elasticloadbalancing:us-east-1:758888582357:listener-rule/app/busyb-alb/5111c2db275a2af3/55b0b891b903df23/92304d50b03b02d4

# Create new rule with correct pattern
aws elbv2 create-rule \
  --listener-arn $LISTENER_ARN \
  --priority 50 \
  --conditions Field=path-pattern,Values='/mcp/google-workspace*' \
  --actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:758888582357:targetgroup/busyb-google-workspace/32e64755db77f32e
```

**Option 2: Add ROOT_PATH Environment Variable**
```bash
# Update task definition to add ROOT_PATH
# Edit ecs/task-definition-google-workspace-mcp.json
# Add to environment variables:
{
  "name": "ROOT_PATH",
  "value": "/google-workspace"
}

# Register new task definition
aws ecs register-task-definition \
  --cli-input-json file://ecs/task-definition-google-workspace-mcp.json

# Update service
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-google-workspace-mcp-service \
  --task-definition busyb-google-workspace-mcp \
  --force-new-deployment
```

**Documentation**: See `agent_notes/task_4.8_completion.md` for detailed analysis

---

### 10. Configure Workflow Notifications (Optional)

**Why**: Get notified about deployment success/failure in Slack or email.

**Options**:

**Option A: GitHub Built-in Notifications** (No setup)
- Already works with GitHub account settings
- Configure at: GitHub → Settings → Notifications → Actions

**Option B: Slack Notifications** (Recommended for teams)
1. Create Slack incoming webhook at https://api.slack.com/apps
2. Add webhook URL to GitHub repository secrets:
```bash
# In GitHub repository settings:
# Settings → Secrets and variables → Actions → New repository secret
# Name: SLACK_WEBHOOK_URL
# Value: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

3. Add notification steps to workflow (YAML provided in docs)

**Option C: AWS SNS Email/SMS Notifications**
```bash
# Create SNS topic
aws sns create-topic --name google-workspace-mcp-deployments

# Subscribe to topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments \
  --protocol email \
  --notification-endpoint your-email@example.com
```

4. Add SNS topic ARN to GitHub secrets and update workflow

**Documentation**: See deployment_action_items.md section "Workflow Notifications"

---

### 11. Enable Google Workspace APIs

**Why**: Some tools may require additional API enablement.

**Action Required**:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project
3. Navigate to: APIs & Services → Library
4. Enable these APIs if not already enabled:
   - ✅ Gmail API
   - ✅ Google Drive API
   - ✅ Google Calendar API
   - ✅ Google Docs API
   - ✅ Google Sheets API
   - ✅ Google Slides API
   - ✅ Google Forms API
   - ✅ Google Tasks API
   - ✅ Google Chat API
   - ✅ Custom Search API (if using search tools)

**How to Check**:
```bash
# Test each API after OAuth authentication
# If you get API_NOT_ENABLED errors, enable that API in Google Cloud Console
```

**Documentation**: See `docs/configuration.md` section "Enable APIs"

---

### 12. Configure Google Custom Search (If Using Search Tools)

**Why**: Google Custom Search requires API key and search engine ID.

**Action Required** (only if using search functionality):
1. Get API key: [Google Developers Console](https://console.developers.google.com/)
2. Create search engine: [Programmable Search Engine](https://programmablesearchengine.google.com/)
3. Update task definition with environment variables:

```bash
# Edit ecs/task-definition-google-workspace-mcp.json
# Add to environment variables:
{
  "name": "GOOGLE_PSE_API_KEY",
  "value": "your-api-key"
},
{
  "name": "GOOGLE_PSE_ENGINE_ID",
  "value": "your-engine-id"
}

# Or store in Secrets Manager for better security:
aws secretsmanager create-secret \
  --name busyb/google-pse-api-key \
  --secret-string "your-api-key"

aws secretsmanager create-secret \
  --name busyb/google-pse-engine-id \
  --secret-string "your-engine-id"
```

**Documentation**: See `docs/configuration.md` section "Custom Search Configuration"

---

## 📊 Verification Checklist

After completing manual actions, verify everything works:

### Infrastructure Verification
```bash
# 1. Check ECS service is healthy
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# 2. Check tasks are healthy
aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-google-workspace-mcp-service \
  --desired-status RUNNING

# 3. Check CloudWatch logs for errors
aws logs tail /ecs/busyb-google-workspace-mcp \
  --since 5m \
  --region us-east-1 | grep -i error

# 4. Check service discovery
# (From within VPC - EC2 or ECS Exec)
# nslookup google-workspace.busyb.local
# curl http://google-workspace.busyb.local:8000/health
```

### Functional Verification
```bash
# 5. Test health endpoint
curl http://google-workspace.busyb.local:8000/health

# Expected response:
{
  "status": "healthy",
  "service": "workspace-mcp",
  "version": "1.2.0",
  "transport": "streamable-http"
}

# 6. Verify OAuth flow (follow test procedures)
# 7. Test critical tools (Gmail, Drive, Calendar)
# 8. Verify credentials stored in S3
```

---

## 📝 Summary of Required Actions

### ⏰ Before Production (Critical - Do First)
- [ ] 1. Verify Google OAuth credentials in Secrets Manager
- [ ] 2. Verify S3 credential storage configuration
- [ ] 3. Execute OAuth authentication testing (1-2 hours)
- [ ] 4. Test critical Google Workspace tools (2-4 hours)

### 📅 Week 1 (Important - Do Soon)
- [ ] 5. Configure basic CloudWatch alarms
- [ ] 6. Scale to 2 tasks for redundancy
- [ ] 7. Test rollback procedure
- [ ] 8. Execute performance baseline testing

### 🎯 Optional (When Needed)
- [ ] 9. Fix ALB path prefix issue (if external access needed)
- [ ] 10. Configure workflow notifications
- [ ] 11. Enable additional Google Workspace APIs (if needed)
- [ ] 12. Configure Google Custom Search (if using search tools)

---

## 📚 Documentation References

**Complete test procedures**:
- `agent_notes/task_5.2_oauth_test_procedure.md` - OAuth testing
- `agent_notes/task_5.3-5.6_tools_test_procedures.md` - Tools testing
- `agent_notes/task_5.7-5.8_cicd_rollback_procedures.md` - CI/CD & rollback
- `agent_notes/task_5.9_performance_testing.md` - Performance testing

**Operations guides**:
- `docs/runbook.md` - Production operations manual
- `docs/operations.md` - Complete operations guide
- `docs/monitoring-plan.md` - Monitoring and alerting strategy

**Configuration**:
- `docs/configuration.md` - Environment variables and setup
- `docs/deployment.md` - AWS ECS deployment guide

**Quick reference**:
- `agent_notes/PROJECT_COMPLETION_SUMMARY.md` - Overall project summary
- `deployment_action_items.md` - This tracking document

---

## 🆘 Getting Help

**If you encounter issues**:
1. Check `docs/runbook.md` - Troubleshooting section
2. Check CloudWatch logs: `/ecs/busyb-google-workspace-mcp`
3. Review relevant documentation in `docs/` folder
4. Check GitHub Issues: https://github.com/busyb-ai/google_workspace_mcp/issues

**Service Health**:
```bash
# Quick health check command
aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --region us-east-1 \
  --query 'services[0].events[0:5]'
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-12
**Next Review**: After completing critical actions
