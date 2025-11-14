# Task 5.1: Update Core Agent Configuration - Completion Summary

## Overview

Successfully updated the Core Agent ECS task definition to include the Google Workspace MCP service URL, enabling the Core Agent to connect to and use Google Workspace tools.

## Date

November 12, 2025

## Actions Completed

### 1. Identified Core Agent Configuration

- **Service**: `busyb-core-agent-service`
- **Cluster**: `busyb-cluster`
- **Current Task Definition**: `busyb-core-agent:2`
- **Container**: `busyb-core-agent`

### 2. Downloaded Current Task Definition

```bash
aws ecs describe-task-definition \
  --task-definition busyb-core-agent \
  --query 'taskDefinition' \
  --region us-east-1 > /tmp/core-agent-task-def.json
```

### 3. Added Environment Variable

Added the following environment variable to the task definition:

```json
{
  "name": "MCP_GOOGLE_WORKSPACE_URL",
  "value": "http://google-workspace.busyb.local:8000/mcp"
}
```

This follows the same pattern as existing MCP service integrations:
- `MCP_QUICKBOOKS_URL`: `http://busyb-quickbooks-mcp.busyb.local:8080/mcp`
- `MCP_RESEARCH_URL`: `http://busyb-research-mcp.busyb.local:8080/mcp`
- `MCP_JOBBER_URL`: `http://busyb-jobber-mcp.busyb.local:8080/mcp`

### 4. Registered New Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file:///tmp/core-agent-task-def-clean.json \
  --region us-east-1
```

**Result**: Created task definition revision 3 (`busyb-core-agent:3`)

### 5. Updated Service

```bash
aws ecs update-service \
  --cluster busyb-cluster \
  --service busyb-core-agent-service \
  --task-definition busyb-core-agent:3 \
  --force-new-deployment \
  --region us-east-1
```

### 6. Waited for Service Stabilization

```bash
aws ecs wait services-stable \
  --cluster busyb-cluster \
  --services busyb-core-agent-service \
  --region us-east-1
```

**Result**: Service stabilized successfully with new task definition

## Verification

### Service Status

- **Task Definition**: `busyb-core-agent:3` ✓
- **Running Count**: 1 ✓
- **Desired Count**: 1 ✓
- **Status**: ACTIVE ✓

### Environment Variable

Verified the environment variable is correctly set:

```bash
aws ecs describe-task-definition \
  --task-definition busyb-core-agent:3 \
  --query 'taskDefinition.containerDefinitions[0].environment[?name==`MCP_GOOGLE_WORKSPACE_URL`]'
```

```json
[
    {
        "name": "MCP_GOOGLE_WORKSPACE_URL",
        "value": "http://google-workspace.busyb.local:8000/mcp"
    }
]
```

## DNS Resolution Verification (To Be Done)

DNS resolution testing must be performed from within the VPC, as the service discovery DNS (`google-workspace.busyb.local`) is only accessible within the VPC network.

### Method 1: Using ECS Execute Command

If ECS Exec is enabled on the Core Agent task:

```bash
# Get the task ARN
TASK_ARN=$(aws ecs list-tasks \
  --cluster busyb-cluster \
  --service-name busyb-core-agent-service \
  --desired-status RUNNING \
  --region us-east-1 \
  --query 'taskArns[0]' \
  --output text)

# Connect to the container
aws ecs execute-command \
  --cluster busyb-cluster \
  --task $TASK_ARN \
  --container busyb-core-agent \
  --interactive \
  --command "/bin/bash" \
  --region us-east-1

# Inside container, test DNS and connectivity
nslookup google-workspace.busyb.local
curl -f http://google-workspace.busyb.local:8000/health
```

**Current Running Task**: `arn:aws:ecs:us-east-1:758888582357:task/busyb-cluster/4dc5b6244cc24a4b8ede67ef11ec789b`

### Method 2: Test Via Core Agent Application

Since the Core Agent is now configured with `MCP_GOOGLE_WORKSPACE_URL`, it should automatically attempt to connect to the Google Workspace MCP service when needed. Monitor the Core Agent logs for successful connections.

```bash
# View Core Agent logs
aws logs tail /ecs/busyb-core-agent --follow --region us-east-1
```

Look for:
- Successful connections to Google Workspace MCP
- No DNS resolution errors
- No connection timeout errors

### Method 3: From Another Task in Same VPC

Any other ECS task or EC2 instance in the same VPC can test DNS resolution:

```bash
nslookup google-workspace.busyb.local
# Should resolve to the private IP of the Google Workspace MCP task

curl -f http://google-workspace.busyb.local:8000/health
# Should return: {"status":"healthy"}
```

## Configuration Changes

### Task Definition Changes

- **Previous Revision**: `busyb-core-agent:2`
- **New Revision**: `busyb-core-agent:3`
- **Change**: Added `MCP_GOOGLE_WORKSPACE_URL` environment variable

### Service Changes

- **Deployment Status**: New deployment completed successfully
- **Deployment Method**: Rolling update (no downtime)
- **Tasks Updated**: 1 task replaced with new revision

## Files Created

1. `/tmp/core-agent-task-def.json` - Downloaded original task definition
2. `/tmp/core-agent-task-def-clean.json` - Cleaned task definition with new environment variable

## Next Steps

1. **Task 5.2**: Test OAuth Authentication Flow
   - Now that Core Agent is configured with the Google Workspace MCP URL, proceed with testing the OAuth flow

2. **Verify Integration**: Monitor Core Agent logs when Google Workspace tools are invoked to ensure successful communication

3. **Test from Core Agent**: Initiate a Google Workspace tool request through the Core Agent to verify end-to-end integration

## Summary

✅ Core Agent task definition successfully updated with Google Workspace MCP URL
✅ New task definition (revision 3) registered
✅ Core Agent service updated and redeployed with new configuration
✅ Service stabilized with new task running
✅ Environment variable verified in task definition
⚠️ DNS resolution verification pending (requires VPC access)

The Core Agent is now configured to connect to the Google Workspace MCP service via the internal service discovery DNS name. The integration is ready for OAuth testing in Task 5.2.
