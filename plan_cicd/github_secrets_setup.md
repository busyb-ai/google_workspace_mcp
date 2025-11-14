# GitHub Actions Secrets Setup Guide

**Last Updated**: 2025-11-12
**Task**: Phase 1 - Task 1.4: Configure GitHub Actions Secrets
**Repository**: google_workspace_mcp

---

## Overview

This guide provides step-by-step instructions for adding GitHub Actions secrets to the repository. These secrets are required for the CI/CD workflow to build, push Docker images to ECR, and deploy to ECS.

**Important**: GitHub Actions secrets can only be added through the GitHub web interface or GitHub API (with a personal access token). This guide provides the exact values to use based on the existing BusyB infrastructure.

---

## Prerequisites

- Admin access to the GitHub repository
- AWS account access to create/manage IAM users for GitHub Actions
- Access to the infrastructure inventory documented in `infrastructure_inventory.md`

---

## Required GitHub Actions Secrets

The following secrets must be added to the GitHub repository:

| Secret Name | Type | Description | Example Value |
|-------------|------|-------------|---------------|
| `AWS_REGION` | Configuration | AWS region for deployment | `us-east-1` |
| `AWS_ACCOUNT_ID` | Configuration | AWS account ID | `758888582357` |
| `AWS_ACCESS_KEY_ID` | Credential | IAM user access key for GitHub Actions | `AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | Credential | IAM user secret key for GitHub Actions | `wJalrXUtn...` |
| `ECS_CLUSTER` | Configuration | ECS cluster name | `busyb-cluster` |
| `ECS_SERVICE_GOOGLE_WORKSPACE` | Configuration | ECS service name | `busyb-google-workspace-mcp-service` |

---

## Step 1: Create IAM User for GitHub Actions

Before adding secrets to GitHub, you need to create a dedicated IAM user with appropriate permissions.

### 1.1 Create IAM User

```bash
# Set variables
export IAM_USER_NAME="github-actions-google-workspace-mcp"

# Create IAM user
aws iam create-user \
  --user-name ${IAM_USER_NAME} \
  --tags Key=Purpose,Value=GitHubActions Key=Service,Value=GoogleWorkspaceMCP

# Create access key for the user
aws iam create-access-key \
  --user-name ${IAM_USER_NAME}
```

**Important**: Save the `AccessKeyId` and `SecretAccessKey` from the output. You will need these for GitHub secrets.

### 1.2 Create IAM Policy

Create a file `github-actions-policy.json` with the following content:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ECRAuthorizationToken",
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ECRImageManagement",
      "Effect": "Allow",
      "Action": [
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:us-east-1:758888582357:repository/busyb-google-workspace-mcp"
    },
    {
      "Sid": "ECSServiceManagement",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "ecs:RegisterTaskDefinition"
      ],
      "Resource": [
        "arn:aws:ecs:us-east-1:758888582357:service/busyb-cluster/busyb-google-workspace-mcp-service",
        "arn:aws:ecs:us-east-1:758888582357:cluster/busyb-cluster",
        "arn:aws:ecs:us-east-1:758888582357:task-definition/busyb-google-workspace-mcp:*"
      ]
    },
    {
      "Sid": "IAMPassRole",
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": [
        "arn:aws:iam::758888582357:role/ecsTaskExecutionRole",
        "arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role"
      ],
      "Condition": {
        "StringEquals": {
          "iam:PassedToService": "ecs-tasks.amazonaws.com"
        }
      }
    }
  ]
}
```

### 1.3 Attach Policy to User

```bash
# Create the policy
aws iam create-policy \
  --policy-name GitHubActionsGoogleWorkspaceMCPPolicy \
  --policy-document file://github-actions-policy.json \
  --description "Policy for GitHub Actions to deploy Google Workspace MCP"

# Attach policy to user
aws iam attach-user-policy \
  --user-name ${IAM_USER_NAME} \
  --policy-arn arn:aws:iam::758888582357:policy/GitHubActionsGoogleWorkspaceMCPPolicy
```

### 1.4 Verify IAM User Setup

```bash
# List attached policies
aws iam list-attached-user-policies --user-name ${IAM_USER_NAME}

# Verify access key was created
aws iam list-access-keys --user-name ${IAM_USER_NAME}
```

---

## Step 2: Add Secrets to GitHub Repository

### 2.1 Navigate to GitHub Secrets Settings

1. Go to the GitHub repository: `https://github.com/YOUR_ORG/google_workspace_mcp`
2. Click on **Settings** (top right)
3. In the left sidebar, navigate to **Secrets and variables** > **Actions**
4. You should see the "Repository secrets" section

### 2.2 Add Each Secret

Click **"New repository secret"** and add each of the following secrets one by one:

#### Secret 1: AWS_REGION

- **Name**: `AWS_REGION`
- **Value**: `us-east-1`
- Click **"Add secret"**

#### Secret 2: AWS_ACCOUNT_ID

- **Name**: `AWS_ACCOUNT_ID`
- **Value**: `758888582357`
- Click **"Add secret"**

#### Secret 3: AWS_ACCESS_KEY_ID

- **Name**: `AWS_ACCESS_KEY_ID`
- **Value**: `<AccessKeyId from Step 1.1>`
  - This will be in the format: `AKIA...` (20 characters)
  - Get this from the output of the `create-access-key` command in Step 1.1
- Click **"Add secret"**

#### Secret 4: AWS_SECRET_ACCESS_KEY

- **Name**: `AWS_SECRET_ACCESS_KEY`
- **Value**: `<SecretAccessKey from Step 1.1>`
  - This will be a long string starting with lowercase letters
  - Get this from the output of the `create-access-key` command in Step 1.1
- Click **"Add secret"**

**Security Note**: The secret access key is only shown once during creation. If you lost it, you must create a new access key.

#### Secret 5: ECS_CLUSTER

- **Name**: `ECS_CLUSTER`
- **Value**: `busyb-cluster`
- Click **"Add secret"**

#### Secret 6: ECS_SERVICE_GOOGLE_WORKSPACE

- **Name**: `ECS_SERVICE_GOOGLE_WORKSPACE`
- **Value**: `busyb-google-workspace-mcp-service`
- Click **"Add secret"**

### 2.3 Verify All Secrets Are Added

After adding all secrets, you should see 6 repository secrets listed:

- `AWS_REGION`
- `AWS_ACCOUNT_ID`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `ECS_CLUSTER`
- `ECS_SERVICE_GOOGLE_WORKSPACE`

---

## Step 3: Verify Secrets in Workflow

### 3.1 Test Workflow Configuration

The GitHub Actions workflow will reference these secrets as follows:

```yaml
env:
  AWS_REGION: ${{ secrets.AWS_REGION }}
  ECR_REPOSITORY: busyb-google-workspace-mcp
  ECS_SERVICE: ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }}
  ECS_CLUSTER: ${{ secrets.ECS_CLUSTER }}
  ECS_TASK_DEFINITION: .aws/task-definition.json

jobs:
  deploy:
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}
```

### 3.2 Test Secret Access

You can test that secrets are properly configured by:

1. Creating a simple test workflow that echoes the non-sensitive values
2. Checking the workflow run logs to verify secrets are accessible
3. Running the actual deployment workflow once Phase 4 is complete

---

## IAM Permissions Summary

The IAM user created for GitHub Actions has the following permissions:

### ECR Permissions
- `ecr:GetAuthorizationToken` - Get authentication token for Docker login
- `ecr:BatchCheckLayerAvailability` - Check if image layers exist
- `ecr:GetDownloadUrlForLayer` - Get download URLs for layers
- `ecr:BatchGetImage` - Retrieve image manifests
- `ecr:PutImage` - Push new images
- `ecr:InitiateLayerUpload` - Start uploading image layers
- `ecr:UploadLayerPart` - Upload parts of image layers
- `ecr:CompleteLayerUpload` - Finalize layer uploads

### ECS Permissions
- `ecs:UpdateService` - Update ECS service to deploy new task definition
- `ecs:DescribeServices` - Get service details
- `ecs:DescribeTaskDefinition` - Get task definition details
- `ecs:RegisterTaskDefinition` - Register new task definition revision

### IAM Permissions
- `iam:PassRole` - Allow ECS to assume task execution and task roles (with condition)

**Principle of Least Privilege**: This IAM user has only the minimum permissions required for CI/CD operations. It cannot:
- Delete ECR repositories
- Stop or delete ECS services
- Modify IAM roles or policies
- Access Secrets Manager or S3 directly
- Modify VPC, ALB, or other infrastructure

---

## Security Best Practices

### IAM User Security

1. **Rotate Access Keys Regularly**
   - Set a calendar reminder to rotate GitHub Actions access keys every 90 days
   - When rotating:
     ```bash
     # Create new access key
     aws iam create-access-key --user-name github-actions-google-workspace-mcp

     # Update GitHub secret with new key
     # (via GitHub web interface)

     # Delete old access key
     aws iam delete-access-key \
       --user-name github-actions-google-workspace-mcp \
       --access-key-id <OLD_KEY_ID>
     ```

2. **Monitor Access Key Usage**
   ```bash
   # Check last used time for access keys
   aws iam get-access-key-last-used \
     --access-key-id <ACCESS_KEY_ID>
   ```

3. **Enable CloudTrail Logging**
   - Ensure CloudTrail is enabled to audit all API calls made by this IAM user
   - Review logs regularly for suspicious activity

### GitHub Secrets Security

1. **Limit Access to Repository Secrets**
   - Only repository admins should have access to manage secrets
   - Review repository collaborators regularly

2. **Use Environment Protection Rules**
   - Consider setting up environment-specific secrets (dev, staging, prod)
   - Use GitHub environment protection rules to require approvals for production deployments

3. **Avoid Exposing Secrets in Logs**
   - Never echo or print secret values in workflow logs
   - GitHub automatically masks secrets in logs, but avoid explicitly printing them

4. **Audit Secret Access**
   - Review GitHub Actions workflow runs regularly
   - Check for failed authentication attempts
   - Monitor AWS CloudTrail for API calls from this IAM user

---

## Troubleshooting

### Issue: "Access Denied" Error in GitHub Actions

**Symptom**: Workflow fails with "Access Denied" or "403 Forbidden" error

**Solutions**:
1. Verify IAM policy is attached to the user:
   ```bash
   aws iam list-attached-user-policies --user-name github-actions-google-workspace-mcp
   ```

2. Check that the access key is active:
   ```bash
   aws iam list-access-keys --user-name github-actions-google-workspace-mcp
   ```

3. Verify the secret values in GitHub match the IAM user's access keys

4. Check IAM policy JSON for typos in resource ARNs

### Issue: "Invalid AWS Credentials" Error

**Symptom**: Workflow fails with "Invalid AWS credentials" error

**Solutions**:
1. Verify `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are correctly set in GitHub secrets
2. Check if access key has been deactivated or deleted
3. Ensure no extra whitespace in secret values
4. Create a new access key and update GitHub secrets

### Issue: "Cannot Pass Role" Error

**Symptom**: Workflow fails when registering task definition with "User is not authorized to perform: iam:PassRole"

**Solutions**:
1. Verify IAM policy includes the `iam:PassRole` permission
2. Check that the role ARNs in the policy match the roles used in the task definition
3. Ensure the condition `iam:PassedToService: ecs-tasks.amazonaws.com` is present

### Issue: Secret Not Found in Workflow

**Symptom**: Workflow shows empty values for secrets

**Solutions**:
1. Verify secrets are added to the correct repository
2. Check secret names match exactly (case-sensitive)
3. Ensure you're not trying to access secrets from a forked repository (not allowed by default)
4. For pull requests from forks, secrets are not available (security feature)

---

## Checklist

Use this checklist to verify Task 1.4 is complete:

- [ ] IAM user created: `github-actions-google-workspace-mcp`
- [ ] IAM policy created and attached to user
- [ ] Access key created for IAM user (and saved securely)
- [ ] IAM user permissions verified (can access ECR and ECS)
- [ ] GitHub secret `AWS_REGION` added with value `us-east-1`
- [ ] GitHub secret `AWS_ACCOUNT_ID` added with value `758888582357`
- [ ] GitHub secret `AWS_ACCESS_KEY_ID` added with IAM user access key
- [ ] GitHub secret `AWS_SECRET_ACCESS_KEY` added with IAM user secret key
- [ ] GitHub secret `ECS_CLUSTER` added with value `busyb-cluster`
- [ ] GitHub secret `ECS_SERVICE_GOOGLE_WORKSPACE` added with value `busyb-google-workspace-mcp-service`
- [ ] All 6 secrets visible in GitHub repository settings
- [ ] IAM user details documented in `infrastructure_inventory.md`
- [ ] Security best practices reviewed and calendar reminders set

---

## Documentation Updates

After completing this task, update the following files:

1. **`infrastructure_inventory.md`**:
   - Add IAM user name and ARN to the "IAM Roles & Policies" section
   - Document the policy ARN

2. **`deployment_action_items.md`**:
   - Add note about IAM user access key rotation schedule
   - Document any issues encountered during setup

3. **`phase_1.md`**:
   - Mark Task 1.4 as complete in the checklist

---

## Next Steps

After completing Task 1.4:

1. Proceed to **Task 1.5**: Create CloudWatch Log Group
2. Continue with **Task 1.6**: Verify IAM Task Roles (will need to create `busyb-google-workspace-mcp-task-role`)
3. In Phase 4, the GitHub Actions workflow will use these secrets to deploy the service

---

## References

- [GitHub Actions Encrypted Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [GitHub Actions AWS Credentials](https://github.com/aws-actions/configure-aws-credentials)
- Infrastructure inventory: `plan_cicd/infrastructure_inventory.md`
- Phase 1 plan: `plan_cicd/phase_1.md`
