# Phase 1: Prerequisites & AWS Setup

## Overview

This phase focuses on setting up the foundational AWS infrastructure needed for deploying the Google Workspace MCP server. We'll create the ECR repository, configure secrets in AWS Secrets Manager, set up GitHub secrets, and prepare the CloudWatch log group. This phase reuses existing BusyB infrastructure (VPC, subnets, security groups, ALB, S3 bucket) and only creates new resources specific to the Google Workspace MCP service.

## Objectives

- Create ECR repository for Docker images
- Configure Google OAuth credentials in AWS Secrets Manager
- Set up GitHub Actions secrets for CI/CD
- Create CloudWatch Log Group for container logs
- Verify existing infrastructure compatibility

## Prerequisites

- AWS CLI configured with appropriate credentials
- Access to AWS account with permissions for ECR, Secrets Manager, CloudWatch
- GitHub repository access with admin permissions for secrets
- Google OAuth credentials (Client ID and Client Secret)
- Knowledge of existing BusyB infrastructure (VPC ID, subnet IDs, security group IDs)

## Time Estimate

**Total Phase Time**: 2-3 hours

---

## Tasks

### Task 1.1: Verify Existing AWS Infrastructure

**Complexity**: Small
**Estimated Time**: 30 minutes

**Description**:
Verify that the existing BusyB AWS infrastructure (VPC, subnets, security groups, S3 bucket, ALB) is compatible with the Google Workspace MCP deployment requirements.

**Actions**:
- Document existing infrastructure resources:
  - VPC ID and CIDR blocks
  - Public and private subnet IDs
  - Security group IDs (ECS and ALB)
  - S3 bucket name for OAuth tokens (e.g., `busyb-oauth-tokens`)
  - ALB ARN and DNS name
  - NAT Gateway configuration
  - ECS cluster name (should be `busyb-cluster`)
- Run AWS CLI commands to verify resources:
  ```bash
  # Verify VPC
  aws ec2 describe-vpcs --vpc-ids vpc-xxx

  # Verify subnets
  aws ec2 describe-subnets --subnet-ids subnet-xxx subnet-yyy

  # Verify security groups
  aws ec2 describe-security-groups --group-ids sg-xxx sg-yyy

  # Verify S3 bucket
  aws s3 ls s3://busyb-oauth-tokens

  # Verify ECS cluster
  aws ecs describe-clusters --clusters busyb-cluster

  # Verify ALB
  aws elbv2 describe-load-balancers --load-balancer-arns arn:aws:elasticloadbalancing:...
  ```
- Document any missing resources or configuration issues
- Create a reference document with all resource IDs for use in later phases

**Deliverables**:
- `plan_cicd/infrastructure_inventory.md` - Document with all resource IDs and configurations
- Verification that existing infrastructure meets requirements

**Dependencies**: None

---

### Task 1.2: Create ECR Repository

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Create an Amazon ECR repository to store Docker images for the Google Workspace MCP server.

**Actions**:
- Set environment variables:
  ```bash
  export ECR_REPO_NAME="busyb-google-workspace-mcp"
  export AWS_REGION="us-east-1"
  ```
- Create ECR repository:
  ```bash
  aws ecr create-repository \
    --repository-name ${ECR_REPO_NAME} \
    --region ${AWS_REGION} \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256
  ```
- Set lifecycle policy to keep last 10 images:
  ```bash
  aws ecr put-lifecycle-policy \
    --repository-name ${ECR_REPO_NAME} \
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
- Document the ECR repository URI (format: `<account-id>.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp`)

**Deliverables**:
- ECR repository created: `busyb-google-workspace-mcp`
- Lifecycle policy configured
- Repository URI documented in `plan_cicd/infrastructure_inventory.md`

**Dependencies**: Task 1.1

---

### Task 1.3: Configure AWS Secrets Manager

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Store Google OAuth credentials in AWS Secrets Manager for secure access by ECS tasks.

**Actions**:
- Prepare Google OAuth credentials (from Google Cloud Console)
- Create secret for Google OAuth Client ID:
  ```bash
  aws secretsmanager create-secret \
    --name busyb/google-oauth-client-id \
    --description "Google OAuth Client ID for Workspace MCP" \
    --secret-string "your-google-client-id.apps.googleusercontent.com" \
    --region us-east-1
  ```
- Create secret for Google OAuth Client Secret:
  ```bash
  aws secretsmanager create-secret \
    --name busyb/google-oauth-client-secret \
    --description "Google OAuth Client Secret for Workspace MCP" \
    --secret-string "your-google-client-secret" \
    --region us-east-1
  ```
- Verify existing secret for S3 credentials bucket:
  ```bash
  aws secretsmanager describe-secret \
    --secret-id busyb/s3-credentials-bucket \
    --region us-east-1
  ```
- Document secret ARNs for use in ECS task definition

**Deliverables**:
- AWS Secrets Manager secrets created:
  - `busyb/google-oauth-client-id`
  - `busyb/google-oauth-client-secret`
- Secret ARNs documented in `plan_cicd/infrastructure_inventory.md`
- Verification that `busyb/s3-credentials-bucket` exists

**Dependencies**: Task 1.1

**Security Note**: Never commit actual secret values to version control. Use placeholder values in documentation.

---

### Task 1.4: Configure GitHub Actions Secrets

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Add AWS credentials and configuration values to GitHub repository secrets for use in CI/CD workflow.

**Actions**:
- Navigate to GitHub repository settings: `Settings > Secrets and variables > Actions`
- Add the following repository secrets:
  - `AWS_REGION`: `us-east-1`
  - `AWS_ACCOUNT_ID`: Your AWS account ID (e.g., `123456789012`)
  - `AWS_ACCESS_KEY_ID`: IAM user access key for GitHub Actions
  - `AWS_SECRET_ACCESS_KEY`: IAM user secret key for GitHub Actions
  - `ECS_CLUSTER`: `busyb-cluster`
  - `ECS_SERVICE_GOOGLE_WORKSPACE`: `busyb-google-workspace-mcp-service`
- Verify IAM user permissions include:
  - ECR: `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`
  - ECS: `ecs:UpdateService`, `ecs:DescribeServices`
- Document which IAM user/role is being used for GitHub Actions

**Deliverables**:
- GitHub Actions secrets configured
- IAM permissions verified
- Documentation of IAM user/role in `plan_cicd/infrastructure_inventory.md`

**Dependencies**: Task 1.2, Task 1.3

**Security Note**: Ensure IAM user follows principle of least privilege and has only the permissions listed above.

---

### Task 1.5: Create CloudWatch Log Group

**Complexity**: Small
**Estimated Time**: 10 minutes

**Description**:
Create a CloudWatch Log Group for ECS container logs with appropriate retention policy.

**Actions**:
- Create log group:
  ```bash
  aws logs create-log-group \
    --log-group-name /ecs/busyb-google-workspace-mcp \
    --region us-east-1
  ```
- Set retention policy to 30 days (MVP setting):
  ```bash
  aws logs put-retention-policy \
    --log-group-name /ecs/busyb-google-workspace-mcp \
    --retention-in-days 30 \
    --region us-east-1
  ```
- Add tags to log group:
  ```bash
  aws logs tag-log-group \
    --log-group-name /ecs/busyb-google-workspace-mcp \
    --tags Environment=production,Service=google-workspace-mcp,ManagedBy=terraform
  ```
- Verify log group creation:
  ```bash
  aws logs describe-log-groups \
    --log-group-name-prefix /ecs/busyb-google-workspace-mcp
  ```

**Deliverables**:
- CloudWatch Log Group created: `/ecs/busyb-google-workspace-mcp`
- Retention policy set to 30 days
- Log group ARN documented in `plan_cicd/infrastructure_inventory.md`

**Dependencies**: Task 1.1

---

### Task 1.6: Verify IAM Task Roles

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Verify that existing IAM roles for ECS tasks have the necessary permissions for S3 access and Secrets Manager access.

**Actions**:
- Verify ECS Task Execution Role exists and has permissions:
  ```bash
  aws iam get-role --role-name ecsTaskExecutionRole
  aws iam list-attached-role-policies --role-name ecsTaskExecutionRole
  ```
  - Should have `AmazonECSTaskExecutionRolePolicy` attached
  - Should have permissions for Secrets Manager and ECR
- Verify or create ECS Task Role (`busyb-mcp-task-role`) with S3 and Secrets Manager permissions:
  ```bash
  # Check if role exists
  aws iam get-role --role-name busyb-mcp-task-role
  ```
- If role doesn't exist, create policy document `task-role-policy.json`:
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
- Create or update IAM role with this policy
- Document role ARNs for use in ECS task definition

**Deliverables**:
- Verification that `ecsTaskExecutionRole` exists with correct permissions
- `busyb-mcp-task-role` created or verified with S3 and Secrets Manager permissions
- Role ARNs documented in `plan_cicd/infrastructure_inventory.md`
- Policy document saved in `plan_cicd/task-role-policy.json`

**Dependencies**: Task 1.3

---

### Task 1.7: Test AWS Credentials and Permissions

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Test that all AWS credentials and permissions are working correctly before proceeding to next phase.

**Actions**:
- Test ECR access:
  ```bash
  aws ecr describe-repositories \
    --repository-names busyb-google-workspace-mcp \
    --region us-east-1
  ```
- Test Secrets Manager access:
  ```bash
  aws secretsmanager get-secret-value \
    --secret-id busyb/google-oauth-client-id \
    --region us-east-1
  ```
- Test S3 bucket access:
  ```bash
  aws s3 ls s3://busyb-oauth-tokens/
  ```
- Test CloudWatch Logs access:
  ```bash
  aws logs describe-log-groups \
    --log-group-name-prefix /ecs/busyb-google-workspace-mcp
  ```
- Test ECS cluster access:
  ```bash
  aws ecs describe-clusters \
    --clusters busyb-cluster \
    --region us-east-1
  ```
- Document any permission issues and resolve them

**Deliverables**:
- Confirmation that all AWS services are accessible
- Any permission issues documented and resolved
- Test results added to `plan_cicd/infrastructure_inventory.md`

**Dependencies**: Task 1.2, Task 1.3, Task 1.5, Task 1.6

---

## Phase 1 Checklist

- [x] Task 1.1: Verify Existing AWS Infrastructure
- [x] Task 1.2: Create ECR Repository
- [x] Task 1.3: Configure AWS Secrets Manager
- [x] Task 1.4: Configure GitHub Actions Secrets
- [x] Task 1.5: Create CloudWatch Log Group
- [x] Task 1.6: Verify IAM Task Roles
- [x] Task 1.7: Test AWS Credentials and Permissions

## Success Criteria

- ECR repository created and configured with lifecycle policy
- Google OAuth credentials stored in AWS Secrets Manager
- GitHub Actions secrets configured
- CloudWatch Log Group created with 30-day retention
- IAM roles verified with correct permissions
- All AWS access tests passing
- Complete infrastructure inventory documented

## Next Steps

Proceed to Phase 2: Dockerfile Review & Optimization
