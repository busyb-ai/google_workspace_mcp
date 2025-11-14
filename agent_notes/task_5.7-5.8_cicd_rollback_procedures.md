# Tasks 5.7-5.8: CI/CD Pipeline and Rollback Testing

## Overview

This document provides comprehensive procedures for testing the automated CI/CD pipeline and rollback capabilities.

---

# Task 5.7: Test Automated CI/CD Pipeline

## Objective

Validate that the complete CI/CD pipeline works correctly:
1. Code changes pushed to `main` trigger GitHub Actions
2. Docker image builds successfully
3. Image pushed to ECR
4. ECS service updated with new image
5. Service remains healthy after deployment

## Previous Experience

We've already validated the CI/CD pipeline during Phase 4 when we:
- Fixed the circular import bug in `auth/scopes.py`
- Committed the fix to `main` branch
- GitHub Actions workflow triggered automatically
- New Docker image built and pushed to ECR
- ECS service updated and became healthy

This test will formalize and document the procedure for future use.

---

## Test Procedure

### Pre-Test Setup

1. **Document Current State**
   ```bash
   # Get current task definition revision
   export CURRENT_REVISION=$(aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query 'services[0].taskDefinition' \
     --output text --region us-east-1 | grep -o '[0-9]*$')

   echo "Current revision before test: $CURRENT_REVISION"

   # Get current task ARN
   export CURRENT_TASK=$(aws ecs list-tasks \
     --cluster busyb-cluster \
     --service-name busyb-google-workspace-mcp-service \
     --desired-status RUNNING \
     --query 'taskArns[0]' \
     --output text --region us-east-1)

   echo "Current task: $CURRENT_TASK"

   # Verify service health
   curl -f http://google-workspace.busyb.local:8000/health
   ```

2. **Check GitHub Actions Status**
   ```bash
   # View recent workflow runs
   gh run list --repo busyb-ai/google_workspace_mcp --limit 5
   ```

---

### Test Case 1: Minor Documentation Change

**Objective**: Verify CI/CD pipeline triggers for minor changes

**Steps**:

1. **Create Test Branch**
   ```bash
   cd /Users/rob/Projects/busyb/google_workspace_mcp
   git checkout main
   git pull origin main
   git checkout -b test/cicd-verification-$(date +%s)
   ```

2. **Make Minor Change**
   ```bash
   # Add timestamp to deployment documentation
   echo "" >> docs/deployment.md
   echo "## CI/CD Test Deployment" >> docs/deployment.md
   echo "" >> docs/deployment.md
   echo "Test deployment on $(date -u +"%Y-%m-%d %H:%M:%S UTC")" >> docs/deployment.md
   echo "" >> docs/deployment.md
   echo "This entry verifies the automated CI/CD pipeline works correctly." >> docs/deployment.md

   git add docs/deployment.md
   git commit -m "test: verify CI/CD pipeline deployment $(date +%Y%m%d)"
   ```

3. **Push and Create PR**
   ```bash
   git push origin HEAD

   # Create PR via GitHub CLI
   gh pr create \
     --title "Test: Verify CI/CD Pipeline" \
     --body "This PR tests the automated CI/CD deployment pipeline.\n\nExpected behavior:\n- GitHub Actions should trigger on merge to main\n- Docker image should build\n- ECS service should update\n- Service should remain healthy" \
     --base main
   ```

4. **Verify No Premature Deployment**
   ```bash
   # Wait 30 seconds
   sleep 30

   # Verify workflow did NOT run (PR not merged yet)
   gh run list --repo busyb-ai/google_workspace_mcp --limit 1

   # Should show no new runs
   ```

5. **Merge PR**
   ```bash
   # Merge via GitHub CLI
   gh pr merge --merge --delete-branch

   # Or via web interface
   ```

6. **Monitor GitHub Actions Workflow**
   ```bash
   # Watch workflow execution
   gh run watch

   # Or view in browser
   # https://github.com/busyb-ai/google_workspace_mcp/actions
   ```

7. **Monitor ECS Deployment**
   ```bash
   # Watch service events
   watch -n 5 'aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query "services[0].events[0:3]" \
     --region us-east-1'
   ```

8. **Verify New Task Running**
   ```bash
   # Wait for deployment to complete (5-10 minutes)
   aws ecs wait services-stable \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1

   # Get new task ARN
   export NEW_TASK=$(aws ecs list-tasks \
     --cluster busyb-cluster \
     --service-name busyb-google-workspace-mcp-service \
     --desired-status RUNNING \
     --query 'taskArns[0]' \
     --output text --region us-east-1)

   echo "New task: $NEW_TASK"

   # Compare with old task
   if [ "$NEW_TASK" != "$CURRENT_TASK" ]; then
     echo "✅ New task deployed successfully"
   else
     echo "❌ Task did not change"
   fi
   ```

9. **Verify Service Health**
   ```bash
   # Test health endpoint
   curl -f http://google-workspace.busyb.local:8000/health | python3 -m json.tool

   # Expected output:
   # {
   #   "status": "healthy",
   #   "service": "workspace-mcp",
   #   "transport": "streamable-http"
   # }
   ```

10. **Verify New Revision**
    ```bash
    export NEW_REVISION=$(aws ecs describe-services \
      --cluster busyb-cluster \
      --services busyb-google-workspace-mcp-service \
      --query 'services[0].taskDefinition' \
      --output text --region us-east-1 | grep -o '[0-9]*$')

    echo "Previous revision: $CURRENT_REVISION"
    echo "New revision: $NEW_REVISION"

    if [ "$NEW_REVISION" -gt "$CURRENT_REVISION" ]; then
      echo "✅ Task definition revision incremented"
    else
      echo "❌ Task definition did not update"
    fi
    ```

11. **Test Tool Functionality**
    ```bash
    # Make a test MCP call to verify service works
    curl -X POST http://google-workspace.busyb.local:8000/mcp \
      -H "Content-Type: application/json" \
      -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
      }' | python3 -m json.tool
    ```

12. **Check CloudWatch Logs**
    ```bash
    # View recent logs
    aws logs tail /ecs/busyb-google-workspace-mcp \
      --since 10m \
      --region us-east-1 | head -50
    ```

**Success Criteria**:
- ✅ GitHub Actions workflow triggered on merge to main
- ✅ Docker build succeeded
- ✅ Image pushed to ECR successfully
- ✅ ECS service updated with new task definition
- ✅ New task started and reached RUNNING state
- ✅ Old task stopped gracefully
- ✅ Health checks passing
- ✅ Service remains functional after deployment
- ✅ Deployment completed within 10 minutes
- ✅ No errors in CloudWatch logs

---

### Test Case 2: Code Change with Functionality Impact

**Objective**: Verify CI/CD handles code changes that affect functionality

**Steps**:

1. **Create Feature Branch**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b test/add-deployment-timestamp
   ```

2. **Add Feature: Health Check Timestamp**
   ```bash
   # Edit core/server.py to add timestamp to health check
   # This is a non-breaking change that adds information
   ```

   Edit the health check endpoint:
   ```python
   @server.custom_route("/health", methods=["GET"])
   async def health_check():
       """Health check endpoint."""
       from datetime import datetime
       return {
           "status": "healthy",
           "service": "workspace-mcp",
           "version": "1.0.0",
           "transport": get_transport_mode(),
           "timestamp": datetime.utcnow().isoformat() + "Z"
       }
   ```

3. **Commit and Push**
   ```bash
   git add core/server.py
   git commit -m "feat: add timestamp to health check endpoint"
   git push origin HEAD
   ```

4. **Create and Merge PR**
   ```bash
   gh pr create \
     --title "feat: Add timestamp to health check" \
     --body "Adds UTC timestamp to health check response for monitoring purposes" \
     --base main

   # Wait for review, then merge
   gh pr merge --merge --delete-branch
   ```

5. **Monitor Deployment** (same as Test Case 1)

6. **Verify New Feature**
   ```bash
   # Test new health check format
   response=$(curl -s http://google-workspace.busyb.local:8000/health)
   echo "$response" | python3 -m json.tool

   # Verify timestamp field exists
   if echo "$response" | grep -q '"timestamp"'; then
     echo "✅ New feature deployed successfully"
   else
     echo "❌ New feature not present"
   fi
   ```

**Success Criteria**:
- ✅ Code change deployed successfully
- ✅ New feature works as expected
- ✅ No breaking changes to existing functionality
- ✅ Service remains stable

---

### Test Case 3: Concurrent Deployments

**Objective**: Verify system handles rapid consecutive deployments

**Note**: This is a stress test and should be done carefully

**Steps**:

1. **Make First Change**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b test/concurrent-1
   echo "# Test 1" >> README.md
   git add README.md
   git commit -m "test: concurrent deployment 1"
   git push origin HEAD
   gh pr create --title "Test 1" --body "Concurrent test 1" --base main
   ```

2. **Immediately Make Second Change**
   ```bash
   git checkout main
   git checkout -b test/concurrent-2
   echo "# Test 2" >> README.md
   git add README.md
   git commit -m "test: concurrent deployment 2"
   git push origin HEAD
   gh pr create --title "Test 2" --body "Concurrent test 2" --base main
   ```

3. **Merge Both PRs Quickly**
   ```bash
   # Merge first
   gh pr merge 1 --merge --delete-branch

   # Wait 30 seconds
   sleep 30

   # Merge second
   gh pr merge 2 --merge --delete-branch
   ```

4. **Observe Deployment Behavior**
   - GitHub Actions should queue second workflow
   - ECS should handle deployment gracefully
   - Service should remain stable throughout

**Success Criteria**:
- ✅ Both deployments complete successfully
- ✅ No conflicts or race conditions
- ✅ Service remains healthy throughout
- ✅ Final state reflects both changes

---

## Deployment Timeline Analysis

**Expected Timeline** (for reference):

| Stage | Duration | Notes |
|-------|----------|-------|
| GitHub Actions Trigger | < 30s | Workflow starts on push to main |
| Checkout & Setup | 30s | Code checkout, dependencies |
| Docker Build | 2-4 min | Build image, install dependencies |
| ECR Push | 30s-1min | Push image to ECR |
| ECS Task Definition Update | < 30s | Register new task definition |
| ECS Service Update | 3-5 min | Stop old task, start new task |
| Health Check Stabilization | 1-2 min | Wait for healthy status |
| **Total** | **8-13 min** | End-to-end deployment time |

---

## Monitoring During Deployment

### GitHub Actions Dashboard

Watch for:
- ✅ Green checkmarks on all steps
- ❌ Red X's indicating failures
- ⏳ Yellow spinner indicating in-progress

### CloudWatch Logs

```bash
# Monitor logs during deployment
aws logs tail /ecs/busyb-google-workspace-mcp \
  --follow \
  --region us-east-1 \
  --filter-pattern "ERROR" # Only show errors
```

### ECS Service Metrics

```bash
# Monitor task count
watch -n 5 'aws ecs describe-services \
  --cluster busyb-cluster \
  --services busyb-google-workspace-mcp-service \
  --query "services[0].[desiredCount, runningCount, pendingCount]" \
  --output table --region us-east-1'
```

---

## Troubleshooting Common Issues

### Issue: Docker Build Fails

**Symptoms**: GitHub Actions fails at "Build Docker image" step

**Checks**:
- Review build logs in GitHub Actions
- Check Dockerfile syntax
- Verify all dependencies in requirements.txt

**Resolution**:
- Fix build error
- Commit fix
- Pipeline will re-run automatically

---

### Issue: ECR Push Fails

**Symptoms**: GitHub Actions fails at "Push to ECR" step

**Checks**:
- Verify ECR repository exists
- Check IAM permissions for GitHub Actions
- Verify AWS credentials in GitHub Secrets

**Resolution**:
- Update IAM policy if needed
- Verify GitHub Secrets are correct
- Re-run workflow

---

### Issue: ECS Service Won't Update

**Symptoms**: New task definition created but service doesn't update

**Checks**:
- Check ECS service status
- Review CloudWatch logs
- Verify task definition is valid

**Resolution**:
- Manually update service if needed
- Check for resource constraints (CPU/memory)

---

### Issue: New Task Fails Health Checks

**Symptoms**: New task starts but fails health checks and is stopped

**Checks**:
- Check CloudWatch logs for application errors
- Verify environment variables
- Test health endpoint manually

**Resolution**:
- Fix application error
- Rollback to previous version (see Task 5.8)
- Deploy fix once identified

---

## CI/CD Test Report Template

```markdown
# CI/CD Pipeline Test Report

**Date**: YYYY-MM-DD
**Tester**: Name
**Pipeline Version**: GitHub Actions workflow v1.0

## Test Summary

| Test Case | Status | Duration | Notes |
|-----------|--------|----------|-------|
| Minor Doc Change | ✅ Pass | 9m 30s | |
| Code Change | ✅ Pass | 10m 15s | |
| Concurrent Deploys | ✅ Pass | 15m 45s | |

## Detailed Results

### Test 1: Minor Documentation Change
- Trigger: Merge to main
- Workflow start: HH:MM:SS
- Build complete: HH:MM:SS (Xm Ys)
- ECR push complete: HH:MM:SS (Xm Ys)
- ECS update complete: HH:MM:SS (Xm Ys)
- Service stable: HH:MM:SS (Xm Ys)
- **Total duration**: Xm Ys
- **Status**: ✅ PASS

### Deployment Verification
- Old task revision: N
- New task revision: N+1
- Health check: ✅ Passing
- Functionality: ✅ Working
- CloudWatch logs: ✅ No errors

## Issues Found

[None / List issues]

## Recommendations

1. Monitor deployment duration over time
2. Set up alerts for failed deployments
3. Consider blue/green deployment for zero downtime

## Sign-off

- Tested by: [Name]
- Date: YYYY-MM-DD
```

---

# Task 5.8: Test Rollback Procedure

## Objective

Validate that we can quickly rollback to a previous version if a deployment causes issues.

---

## Rollback Procedure Documentation

### Quick Rollback (< 5 minutes)

When you need to immediately revert to a previous working version:

```bash
#!/bin/bash
# rollback.sh - Quick rollback to previous ECS task definition

set -e

CLUSTER="busyb-cluster"
SERVICE="busyb-google-workspace-mcp-service"
REGION="us-east-1"

echo "=== ECS Service Rollback ==="
echo ""

# Get current revision
CURRENT=$(aws ecs describe-services \
  --cluster $CLUSTER \
  --services $SERVICE \
  --query 'services[0].taskDefinition' \
  --output text --region $REGION | grep -o '[0-9]*$')

echo "Current revision: $CURRENT"

# Calculate previous revision
PREVIOUS=$((CURRENT - 1))
echo "Rolling back to revision: $PREVIOUS"

# Confirm
read -p "Proceed with rollback? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "Rollback cancelled"
  exit 0
fi

# Update service
echo "Updating service..."
aws ecs update-service \
  --cluster $CLUSTER \
  --service $SERVICE \
  --task-definition busyb-google-workspace-mcp:${PREVIOUS} \
  --force-new-deployment \
  --region $REGION > /dev/null

echo "✅ Service update initiated"
echo ""

# Wait for stable
echo "Waiting for service to stabilize..."
aws ecs wait services-stable \
  --cluster $CLUSTER \
  --services $SERVICE \
  --region $REGION

echo "✅ Service is stable"
echo ""

# Verify health
echo "Checking service health..."
if curl -f -s http://google-workspace.busyb.local:8000/health > /dev/null; then
  echo "✅ Service is healthy"
else
  echo "❌ Service health check failed"
  exit 1
fi

echo ""
echo "=== Rollback Complete ==="
echo "Rolled back from revision $CURRENT to $PREVIOUS"
```

---

## Test Procedure

### Pre-Test Setup

1. **Document Current Working State**
   ```bash
   # Save current revision
   export WORKING_REVISION=$(aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query 'services[0].taskDefinition' \
     --output text --region us-east-1 | grep -o '[0-9]*$')

   echo "Working revision: $WORKING_REVISION"

   # Test current service
   curl http://google-workspace.busyb.local:8000/health
   ```

2. **Create Rollback Script**
   ```bash
   # Save the rollback script above
   cat > rollback.sh << 'EOF'
   [Insert rollback script here]
   EOF

   chmod +x rollback.sh
   ```

---

### Test Case 1: Intentional Breaking Change

**Objective**: Deploy a breaking change and rollback

**Steps**:

1. **Create Breaking Change Branch**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b test/breaking-change-rollback
   ```

2. **Introduce Breaking Change**

   Option A: Invalid Docker CMD
   ```bash
   # Edit Dockerfile
   echo "" >> Dockerfile
   echo "# TEMPORARY BREAKING CHANGE FOR ROLLBACK TEST" >> Dockerfile
   echo "CMD [\"nonexistent-command\"]" >> Dockerfile
   ```

   Option B: Python Syntax Error
   ```bash
   # Edit core/server.py
   echo "# SYNTAX ERROR FOR TESTING" >> core/server.py
   echo "this is invalid python syntax!!!" >> core/server.py
   ```

3. **Commit and Push**
   ```bash
   git add .
   git commit -m "test: introduce breaking change for rollback test"
   git push origin HEAD
   ```

4. **Create and Merge PR**
   ```bash
   gh pr create \
     --title "Test: Breaking Change for Rollback" \
     --body "⚠️ This PR intentionally introduces a breaking change to test rollback procedure" \
     --base main

   gh pr merge --merge --delete-branch
   ```

5. **Monitor Failed Deployment**
   ```bash
   # Watch workflow (will likely succeed build but fail deployment)
   gh run watch

   # Monitor ECS
   watch -n 5 'aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query "services[0].events[0:3]" \
     --region us-east-1'
   ```

6. **Observe Failure Symptoms**
   ```bash
   # Check if new task is failing
   aws ecs list-tasks \
     --cluster busyb-cluster \
     --service-name busyb-google-workspace-mcp-service \
     --desired-status STOPPED \
     --region us-east-1

   # Check CloudWatch logs for errors
   aws logs tail /ecs/busyb-google-workspace-mcp \
     --since 5m \
     --region us-east-1 | grep -i error
   ```

7. **Execute Rollback** ⏱️ START TIMER
   ```bash
   # Run rollback script
   ./rollback.sh
   ```

8. **Verify Rollback** ⏱️ STOP TIMER
   ```bash
   # Check service health
   curl http://google-workspace.busyb.local:8000/health

   # Verify running task revision
   CURRENT_REVISION=$(aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query 'services[0].taskDefinition' \
     --output text --region us-east-1 | grep -o '[0-9]*$')

   if [ "$CURRENT_REVISION" -eq "$WORKING_REVISION" ]; then
     echo "✅ Successfully rolled back to working revision"
   else
     echo "❌ Rollback to wrong revision"
   fi
   ```

9. **Test Service Functionality**
   ```bash
   # Test MCP call
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/list",
       "params": {}
     }'
   ```

10. **Fix Breaking Change**
    ```bash
    # Revert the commit
    git checkout main
    git pull origin main
    git revert HEAD --no-edit
    git push origin main

    # Wait for healthy deployment
    gh run watch
    ```

**Success Criteria**:
- ✅ Breaking change deployed and failed as expected
- ✅ Rollback completed in < 5 minutes
- ✅ Service restored to working state
- ✅ Health checks passing after rollback
- ✅ No data loss or corruption
- ✅ CloudWatch logs show rollback activity

---

### Test Case 2: Rollback Multiple Revisions

**Objective**: Rollback to a revision older than the immediate previous

**Steps**:

1. **List Recent Task Definitions**
   ```bash
   aws ecs list-task-definitions \
     --family-prefix busyb-google-workspace-mcp \
     --sort DESC \
     --max-items 5 \
     --region us-east-1
   ```

2. **Choose Target Revision**
   ```bash
   # Current revision
   CURRENT=$(aws ecs describe-services \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --query 'services[0].taskDefinition' \
     --output text --region us-east-1 | grep -o '[0-9]*$')

   # Target revision (3 versions back)
   TARGET=$((CURRENT - 3))
   echo "Rolling back from $CURRENT to $TARGET"
   ```

3. **Execute Multi-Revision Rollback**
   ```bash
   aws ecs update-service \
     --cluster busyb-cluster \
     --service busyb-google-workspace-mcp-service \
     --task-definition busyb-google-workspace-mcp:${TARGET} \
     --force-new-deployment \
     --region us-east-1

   aws ecs wait services-stable \
     --cluster busyb-cluster \
     --services busyb-google-workspace-mcp-service \
     --region us-east-1
   ```

4. **Verify Rollback**
   ```bash
   curl http://google-workspace.busyb.local:8000/health
   ```

5. **Restore to Latest**
   ```bash
   # Roll forward to latest working revision
   ./rollback.sh # Use script or manual command
   ```

**Success Criteria**:
- ✅ Can rollback to any previous revision
- ✅ Service works correctly after multi-revision rollback
- ✅ Can roll forward to latest version

---

### Test Case 3: Automated Rollback Simulation

**Objective**: Test automated rollback based on health check failures

**Note**: This is a procedure documentation exercise. Actual automation would require additional tooling (e.g., Lambda function, CloudWatch Alarm).

**Automated Rollback Script** (for future implementation):

```bash
#!/bin/bash
# auto-rollback.sh - Automatically rollback on health check failure

CLUSTER="busyb-cluster"
SERVICE="busyb-google-workspace-mcp-service"
HEALTH_URL="http://google-workspace.busyb.local:8000/health"
MAX_RETRIES=5
RETRY_INTERVAL=30

check_health() {
  curl -f -s $HEALTH_URL > /dev/null
  return $?
}

echo "Monitoring service health..."

for i in $(seq 1 $MAX_RETRIES); do
  echo "Health check attempt $i/$MAX_RETRIES"

  if check_health; then
    echo "✅ Service is healthy"
    exit 0
  else
    echo "❌ Health check failed"

    if [ $i -eq $MAX_RETRIES ]; then
      echo "⚠️  Maximum retries reached. Initiating rollback..."

      # Get current and previous revision
      CURRENT=$(aws ecs describe-services \
        --cluster $CLUSTER \
        --services $SERVICE \
        --query 'services[0].taskDefinition' \
        --output text --region us-east-1 | grep -o '[0-9]*$')
      PREVIOUS=$((CURRENT - 1))

      # Rollback
      aws ecs update-service \
        --cluster $CLUSTER \
        --service $SERVICE \
        --task-definition busyb-google-workspace-mcp:${PREVIOUS} \
        --force-new-deployment \
        --region us-east-1

      echo "✅ Rollback initiated to revision $PREVIOUS"
      exit 1
    fi

    echo "Waiting $RETRY_INTERVAL seconds before retry..."
    sleep $RETRY_INTERVAL
  fi
done
```

---

## Rollback Decision Matrix

| Scenario | Rollback Method | Expected Time | Risk Level |
|----------|----------------|---------------|------------|
| Failed health checks | Automatic via script | < 5 min | Low |
| Application errors | Manual rollback | < 5 min | Low |
| Performance degradation | Manual rollback | < 5 min | Medium |
| Security issue | Immediate rollback | < 2 min | High |
| Data corruption | Stop service, investigate | Variable | Critical |

---

## Post-Rollback Procedures

### 1. Investigate Root Cause
```bash
# Collect logs from failed deployment
aws logs get-log-events \
  --log-group-name /ecs/busyb-google-workspace-mcp \
  --log-stream-name <failed-task-stream> \
  --region us-east-1 > failed-deployment-logs.txt

# Review GitHub Actions logs
gh run view <run-id> --log
```

### 2. Document Incident
- What failed?
- When did it fail?
- How was it detected?
- How long until rollback?
- Root cause?
- Prevention steps?

### 3. Fix and Redeploy
```bash
# Create fix branch
git checkout main
git pull origin main
git checkout -b fix/deployment-issue

# Make fixes
# ... edit code ...

# Test locally
docker build -t test .
docker run -p 8000:8000 test

# Commit and deploy
git add .
git commit -m "fix: resolve deployment issue"
git push origin HEAD
gh pr create --title "Fix: Deployment Issue" --body "..." --base main
```

---

## Rollback Test Report Template

```markdown
# Rollback Procedure Test Report

**Date**: YYYY-MM-DD
**Tester**: Name

## Test Summary

| Test Case | Status | Rollback Time | Notes |
|-----------|--------|---------------|-------|
| Breaking Change | ✅ Pass | 3m 45s | |
| Multi-Revision | ✅ Pass | 4m 10s | |

## Detailed Results

### Test 1: Breaking Change Rollback
- Deployment failed: HH:MM:SS
- Rollback initiated: HH:MM:SS
- Service stable: HH:MM:SS
- **Rollback duration**: 3m 45s
- **Status**: ✅ PASS

### Rollback Verification
- Previous revision: N
- Rolled back to: N-1
- Health check: ✅ Passing
- Functionality: ✅ Working
- Data integrity: ✅ Intact

## Issues Found

[None / List issues]

## Recommendations

1. Create automated rollback script
2. Set up health check monitoring
3. Document common failure scenarios
4. Practice rollback regularly

## Sign-off

- Tested by: [Name]
- Approved by: [Name]
- Date: YYYY-MM-DD
```

---

## Emergency Rollback Checklist

For quick reference during incidents:

- [ ] Identify failing revision number
- [ ] Identify last working revision number
- [ ] Run rollback script or manual command
- [ ] Wait for service stabilization (3-5 min)
- [ ] Verify health check passing
- [ ] Test critical functionality
- [ ] Notify stakeholders
- [ ] Collect logs from failed deployment
- [ ] Document incident
- [ ] Create fix for root cause
- [ ] Test fix thoroughly
- [ ] Redeploy with fix

---

## Next Steps

After completing CI/CD and rollback testing:

1. ✅ Document test results
2. ✅ Save rollback script to repository
3. ✅ Update deployment_action_items.md
4. ➡️ Proceed to Task 5.9: Performance and Load Testing
5. ➡️ Create production runbook (Task 5.10)
