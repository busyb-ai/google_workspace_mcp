# Phase 4: ECS Task Definition & Service Creation

## Overview

This phase focuses on creating the ECS task definition and service for running the Google Workspace MCP server on AWS Fargate. We'll configure the container with proper environment variables, secrets, networking, health checks, and service discovery. The service will integrate with the existing BusyB infrastructure (ALB, VPC, security groups) and use the Docker image from ECR.

## Objectives

- Create ECS task definition with proper configuration
- Configure environment variables and secrets injection
- Set up health checks and logging
- Create ALB target group for the service
- Configure service discovery for internal communication
- Create ECS service with ALB integration
- Verify service starts and passes health checks

## Prerequisites

- Completed Phase 1 (AWS infrastructure setup)
- Completed Phase 2 (Production Dockerfile)
- Completed Phase 3 (GitHub Actions workflow)
- Docker image pushed to ECR (at least one build)
- Understanding of ECS task definitions and services
- Knowledge of existing BusyB VPC and ALB configuration

## Context from Previous Phases

From Phase 1:
- ECR repository: `busyb-google-workspace-mcp`
- Secrets in AWS Secrets Manager
- CloudWatch Log Group: `/ecs/busyb-google-workspace-mcp`
- IAM roles: `ecsTaskExecutionRole` and `busyb-mcp-task-role`

From Phase 2:
- Production Dockerfile uses entrypoint script
- Expects environment variables: `MCP_GOOGLE_OAUTH_CLIENT_ID`, `MCP_GOOGLE_OAUTH_CLIENT_SECRET`, `MCP_GOOGLE_CREDENTIALS_DIR`
- Health check endpoint: `GET /health` on port 8000

From Phase 3:
- GitHub Actions workflow ready to deploy
- Images tagged with commit SHA and `latest`

The ECS service will:
- Run in private subnets (no public IP)
- Use Fargate launch type
- Connect to ALB for external access
- Use service discovery for Core Agent communication
- Pull secrets from AWS Secrets Manager
- Log to CloudWatch Logs

## Time Estimate

**Total Phase Time**: 3-4 hours

---

## Tasks

### Task 4.1: Create ECS Task Definition JSON

**Complexity**: Medium
**Estimated Time**: 45 minutes

**Description**:
Create the ECS task definition JSON file with all required configuration for running the Google Workspace MCP container.

**Actions**:
- Create directory for ECS configuration:
  ```bash
  mkdir -p ecs
  ```
- Get AWS account ID and substitute in template:
  ```bash
  export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
  echo "AWS Account ID: $AWS_ACCOUNT_ID"
  ```
- Create `ecs/task-definition-google-workspace-mcp.json`:
  ```json
  {
    "family": "busyb-google-workspace-mcp",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
    "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/busyb-mcp-task-role",
    "containerDefinitions": [
      {
        "name": "busyb-google-workspace-mcp",
        "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest",
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
            "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:busyb/google-oauth-client-id"
          },
          {
            "name": "MCP_GOOGLE_OAUTH_CLIENT_SECRET",
            "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:busyb/google-oauth-client-secret"
          },
          {
            "name": "MCP_GOOGLE_CREDENTIALS_DIR",
            "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:busyb/s3-credentials-bucket"
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
- Replace `<ACCOUNT_ID>` placeholders with actual AWS account ID:
  ```bash
  sed -i.bak "s/<ACCOUNT_ID>/${AWS_ACCOUNT_ID}/g" ecs/task-definition-google-workspace-mcp.json
  rm ecs/task-definition-google-workspace-mcp.json.bak
  ```
- Validate JSON syntax:
  ```bash
  cat ecs/task-definition-google-workspace-mcp.json | python -m json.tool > /dev/null && echo "✓ JSON is valid"
  ```
- Document task definition configuration in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- `ecs/task-definition-google-workspace-mcp.json` created with correct AWS account ID
- JSON syntax validated
- Configuration documented

**Dependencies**: Phase 1 completed

---

### Task 4.2: Register ECS Task Definition

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Register the task definition with AWS ECS.

**Actions**:
- Register the task definition:
  ```bash
  aws ecs register-task-definition \
    --cli-input-json file://ecs/task-definition-google-workspace-mcp.json \
    --region us-east-1
  ```
- Verify registration:
  ```bash
  aws ecs describe-task-definition \
    --task-definition busyb-google-workspace-mcp \
    --region us-east-1
  ```
- Note the task definition ARN and revision number:
  ```bash
  aws ecs describe-task-definition \
    --task-definition busyb-google-workspace-mcp \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text
  ```
- Document the task definition ARN in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- Task definition registered in ECS
- Task definition ARN documented
- Revision 1 of task definition available

**Dependencies**: Task 4.1

---

### Task 4.3: Create ALB Target Group

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Create an Application Load Balancer target group for the Google Workspace MCP service with proper health checks.

**Actions**:
- Get VPC ID from existing infrastructure:
  ```bash
  export VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=tag:Name,Values=busyb-vpc" \
    --query 'Vpcs[0].VpcId' \
    --output text)
  echo "VPC ID: $VPC_ID"
  ```
- Create target group:
  ```bash
  aws elbv2 create-target-group \
    --name busyb-google-workspace \
    --protocol HTTP \
    --port 8000 \
    --vpc-id ${VPC_ID} \
    --target-type ip \
    --health-check-enabled \
    --health-check-path /health \
    --health-check-protocol HTTP \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --matcher HttpCode=200 \
    --region us-east-1
  ```
- Get target group ARN:
  ```bash
  export TG_ARN=$(aws elbv2 describe-target-groups \
    --names busyb-google-workspace \
    --query 'TargetGroups[0].TargetGroupArn' \
    --output text)
  echo "Target Group ARN: $TG_ARN"
  ```
- Add tags to target group:
  ```bash
  aws elbv2 add-tags \
    --resource-arns ${TG_ARN} \
    --tags Key=Name,Value=busyb-google-workspace Key=Service,Value=google-workspace-mcp Key=Environment,Value=production
  ```
- Document target group ARN in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- ALB target group created: `busyb-google-workspace`
- Health check configured for `/health` endpoint
- Target group ARN documented

**Dependencies**: Task 4.1

---

### Task 4.4: Create ALB Listener Rule

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Add a listener rule to the existing Application Load Balancer to route traffic to the Google Workspace MCP target group.

**Actions**:
- Get ALB listener ARN (for HTTPS listener, typically port 443):
  ```bash
  export ALB_LISTENER_ARN=$(aws elbv2 describe-listeners \
    --load-balancer-arn <LOAD_BALANCER_ARN> \
    --query 'Listeners[?Port==`443`].ListenerArn' \
    --output text)
  echo "ALB Listener ARN: $ALB_LISTENER_ARN"
  ```
- Create listener rule for path-based routing:
  ```bash
  aws elbv2 create-rule \
    --listener-arn ${ALB_LISTENER_ARN} \
    --priority 50 \
    --conditions Field=path-pattern,Values='/google-workspace/*' \
    --actions Type=forward,TargetGroupArn=${TG_ARN} \
    --region us-east-1
  ```
- Verify rule creation:
  ```bash
  aws elbv2 describe-rules \
    --listener-arn ${ALB_LISTENER_ARN} \
    --query 'Rules[?Priority==`50`]'
  ```
- Document listener rule configuration in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- ALB listener rule created with priority 50
- Path pattern `/google-workspace/*` routes to target group
- Rule configuration documented

**Dependencies**: Task 4.3

**Note**: If the ALB doesn't have an HTTPS listener or if external access isn't needed, this task can be adjusted or skipped. Service discovery will still allow internal communication from the Core Agent.

---

### Task 4.5: Configure AWS Cloud Map Service Discovery

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Set up AWS Cloud Map service discovery to allow the Core Agent to reach the Google Workspace MCP service at `http://google-workspace.busyb.local:8000/mcp`.

**Actions**:
- Check if Cloud Map namespace exists:
  ```bash
  aws servicediscovery list-namespaces \
    --query 'Namespaces[?Name==`busyb.local`]'
  ```
- If namespace doesn't exist, create it:
  ```bash
  aws servicediscovery create-private-dns-namespace \
    --name busyb.local \
    --vpc ${VPC_ID} \
    --description "Service discovery namespace for BusyB services" \
    --region us-east-1
  ```
- Get namespace ID:
  ```bash
  export NAMESPACE_ID=$(aws servicediscovery list-namespaces \
    --query 'Namespaces[?Name==`busyb.local`].Id' \
    --output text)
  echo "Namespace ID: $NAMESPACE_ID"
  ```
- Create service discovery service:
  ```bash
  aws servicediscovery create-service \
    --name google-workspace \
    --namespace-id ${NAMESPACE_ID} \
    --dns-config "NamespaceId=${NAMESPACE_ID},RoutingPolicy=MULTIVALUE,DnsRecords=[{Type=A,TTL=60},{Type=SRV,TTL=60}]" \
    --health-check-custom-config FailureThreshold=1 \
    --description "Service discovery for Google Workspace MCP" \
    --region us-east-1
  ```
- Get service discovery service ARN:
  ```bash
  export SD_SERVICE_ARN=$(aws servicediscovery list-services \
    --query 'Services[?Name==`google-workspace`].Arn' \
    --output text)
  echo "Service Discovery ARN: $SD_SERVICE_ARN"
  ```
- Document service discovery configuration in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- Cloud Map namespace created or verified: `busyb.local`
- Service discovery service created: `google-workspace.busyb.local`
- Service discovery ARN documented
- DNS resolution will be `google-workspace.busyb.local`

**Dependencies**: Task 4.2

---

### Task 4.6: Create ECS Service

**Complexity**: Large
**Estimated Time**: 45 minutes

**Description**:
Create the ECS service with Fargate launch type, integrating with ALB, service discovery, and VPC networking.

**Actions**:
- Get private subnet IDs:
  ```bash
  export PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Type,Values=private" \
    --query 'Subnets[*].SubnetId' \
    --output text | tr '\t' ',')
  echo "Private Subnets: $PRIVATE_SUBNETS"
  ```
- Get ECS security group ID:
  ```bash
  export ECS_SG=$(aws ec2 describe-security-groups \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=tag:Name,Values=busyb-ecs-sg" \
    --query 'SecurityGroups[0].GroupId' \
    --output text)
  echo "ECS Security Group: $ECS_SG"
  ```
- Create ECS service with all integrations:
  ```bash
  aws ecs create-service \
    --cluster busyb-cluster \
    --service-name busyb-google-workspace-mcp-service \
    --task-definition busyb-google-workspace-mcp \
    --desired-count 1 \
    --launch-type FARGATE \
    --platform-version LATEST \
    --network-configuration "awsvpcConfiguration={subnets=[${PRIVATE_SUBNETS}],securityGroups=[${ECS_SG}],assignPublicIp=DISABLED}" \
    --load-balancers "targetGroupArn=${TG_ARN},containerName=busyb-google-workspace-mcp,containerPort=8000" \
    --service-registries "registryArn=${SD_SERVICE_ARN},containerName=busyb-google-workspace-mcp,containerPort=8000" \
    --enable-execute-command \
    --health-check-grace-period-seconds 60 \
    --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100" \
    --region us-east-1
  ```
- Verify service creation:
  ```bash
  aws ecs describe-services \
    --cluster busyb-cluster \
    --services busyb-google-workspace-mcp-service \
    --region us-east-1
  ```
- Monitor service deployment:
  ```bash
  aws ecs wait services-stable \
    --cluster busyb-cluster \
    --services busyb-google-workspace-mcp-service \
    --region us-east-1
  ```
- Document service ARN and configuration in `plan_cicd/infrastructure_inventory.md`

**Deliverables**:
- ECS service created: `busyb-google-workspace-mcp-service`
- Service running with 1 task (desired count)
- Service integrated with ALB and service discovery
- Service reaches stable state
- Service ARN documented

**Dependencies**: Task 4.2, Task 4.3, Task 4.5

**Note**: If the service fails to stabilize, check CloudWatch logs and task stopped reasons. Common issues include IAM permission errors, secret access failures, or health check failures.

---

### Task 4.7: Verify Service Health

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Verify the ECS service is running correctly, passing health checks, and accessible via both ALB and service discovery.

**Actions**:
- Check ECS service status:
  ```bash
  aws ecs describe-services \
    --cluster busyb-cluster \
    --services busyb-google-workspace-mcp-service \
    --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:5]}' \
    --region us-east-1
  ```
- List running tasks:
  ```bash
  aws ecs list-tasks \
    --cluster busyb-cluster \
    --service-name busyb-google-workspace-mcp-service \
    --desired-status RUNNING \
    --region us-east-1
  ```
- Get task details and check health status:
  ```bash
  export TASK_ARN=$(aws ecs list-tasks \
    --cluster busyb-cluster \
    --service-name busyb-google-workspace-mcp-service \
    --desired-status RUNNING \
    --query 'taskArns[0]' \
    --output text)

  aws ecs describe-tasks \
    --cluster busyb-cluster \
    --tasks ${TASK_ARN} \
    --query 'tasks[0].{Health:healthStatus,LastStatus:lastStatus,Containers:containers[0].healthStatus}' \
    --region us-east-1
  ```
- Check ALB target health:
  ```bash
  aws elbv2 describe-target-health \
    --target-group-arn ${TG_ARN} \
    --region us-east-1
  ```
- View CloudWatch logs:
  ```bash
  aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1
  ```
- Test service discovery resolution (from within VPC):
  ```bash
  # This would need to be run from an EC2 instance or ECS task in the same VPC
  # nslookup google-workspace.busyb.local
  # curl http://google-workspace.busyb.local:8000/health
  ```
- Document service health status and any issues found

**Deliverables**:
- Service status confirmed as ACTIVE and RUNNING
- Task health check passing (HEALTHY status)
- ALB target health is HEALTHY
- CloudWatch logs showing no errors
- Service discovery DNS resolution works
- Health check endpoint returns 200 OK

**Dependencies**: Task 4.6

---

### Task 4.8: Test External Access via ALB

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Test external access to the Google Workspace MCP service through the Application Load Balancer.

**Actions**:
- Get ALB DNS name:
  ```bash
  export ALB_DNS=$(aws elbv2 describe-load-balancers \
    --query 'LoadBalancers[?contains(LoadBalancerName, `busyb`)].DNSName' \
    --output text)
  echo "ALB DNS: $ALB_DNS"
  ```
- Test health endpoint via ALB:
  ```bash
  curl -i http://${ALB_DNS}/google-workspace/health
  # Or if HTTPS:
  curl -i https://${ALB_DNS}/google-workspace/health
  ```
- Expected response:
  ```json
  {
    "status": "healthy",
    "service": "workspace-mcp",
    "version": "1.2.0",
    "transport": "streamable-http"
  }
  ```
- Test OAuth authorization endpoint (should return HTML page or redirect):
  ```bash
  curl -i https://${ALB_DNS}/google-workspace/oauth2/authorize
  ```
- Document ALB access URL and test results

**Deliverables**:
- External access via ALB confirmed working
- Health endpoint returns 200 OK
- ALB routing to correct target group
- Public URL documented for team use

**Dependencies**: Task 4.7

**Note**: If using path-based routing `/google-workspace/*`, the application may need to be configured to handle the path prefix, or ALB path rewriting may be needed.

---

### Task 4.9: Document ECS Service Configuration

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Document the complete ECS service configuration, deployment procedures, and troubleshooting steps.

**Actions**:
- Update `docs/deployment.md` with ECS service details:
  - Task definition configuration
  - Service configuration
  - Networking setup
  - Health check configuration
  - Service discovery setup
  - ALB integration
- Create operational runbook in `docs/operations.md`:
  - How to view service status
  - How to view logs
  - How to scale the service
  - How to update the service
  - How to troubleshoot common issues
- Add ECS service information to `plan_cicd/infrastructure_inventory.md`:
  - Service ARN
  - Task definition ARN
  - Target group ARN
  - Service discovery ARN
  - Security group IDs
  - Subnet IDs
- Document rollback procedure

**Deliverables**:
- `docs/deployment.md` updated with ECS configuration
- `docs/operations.md` created with operational procedures
- `plan_cicd/infrastructure_inventory.md` updated with all ARNs
- Team has clear documentation for managing the service

**Dependencies**: Task 4.8

---

## Phase 4 Checklist

- [x] Task 4.1: Create ECS Task Definition JSON
- [x] Task 4.2: Register ECS Task Definition
- [x] Task 4.3: Create ALB Target Group
- [x] Task 4.4: Create ALB Listener Rule
- [x] Task 4.5: Configure AWS Cloud Map Service Discovery
- [x] Task 4.6: Create ECS Service
- [x] Task 4.7: Verify Service Health
- [x] Task 4.8: Test External Access via ALB
- [x] Task 4.9: Document ECS Service Configuration

## Success Criteria

- ECS task definition registered successfully
- ECS service created and running
- Service has 1 running task in HEALTHY status
- ALB target group health checks passing
- Service discovery DNS resolution works
- External access via ALB works
- CloudWatch logs showing no errors
- Health endpoint returns 200 OK
- Complete documentation available

## Common Issues and Solutions

### Issue: Task fails to start

**Symptoms**: Tasks start but immediately stop

**Check**:
```bash
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks <TASK_ARN> \
  --query 'tasks[0].stoppedReason'
```

**Common Causes**:
- IAM permission issues (can't pull image, can't access secrets)
- Invalid environment variable values
- Health check failures
- Application startup errors

**Solution**: Check CloudWatch logs, verify IAM permissions, check Secrets Manager access

### Issue: Health checks failing

**Symptoms**: Tasks keep restarting, target health is UNHEALTHY

**Check**:
- CloudWatch logs for application errors
- Health check configuration (path, port, interval)
- Security group allows traffic on port 8000

**Solution**: Adjust health check grace period, verify application starts correctly, check security groups

### Issue: Can't access via service discovery

**Symptoms**: DNS resolution fails or connection refused

**Check**:
- Service discovery service exists
- VPC DNS resolution enabled
- Security groups allow traffic between services

**Solution**: Verify Cloud Map configuration, check VPC DNS settings, update security groups

## Next Steps

Proceed to Phase 5: Integration & Testing
