# Deployment Action Items

**Last Updated**: 2025-11-12
**Project**: Google Workspace MCP Server Deployment

---

## Overview

This document tracks action items and important notes discovered during the deployment process that require manual verification or action by the team.

---

## Phase 1: Prerequisites & AWS Setup

### Task 1.3: Configure AWS Secrets Manager

**Status**: ✅ COMPLETE (with action items)

#### Secrets Status

All required secrets now exist in AWS Secrets Manager:

| Secret Name | Secret ARN | Status | Created |
|-------------|------------|--------|---------|
| `busyb/google-oauth-client-id` | `arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx` | ✅ Exists | 2025-10-28 |
| `busyb/google-oauth-client-secret` | `arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z` | ✅ Exists | 2025-10-28 |
| `busyb/s3-credentials-bucket` | `arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM` | ✅ Created | 2025-11-12 |

#### Secret Value Format

**Important**: The Google OAuth secrets are stored as JSON objects, not plain strings:

- **`busyb/google-oauth-client-id`**:
  ```json
  {
    "GOOGLE_OAUTH_CLIENT_ID": "359995978669-8tfgeen6d1eo89jvpv6tggto7vml22an.apps.googleusercontent.com"
  }
  ```

- **`busyb/google-oauth-client-secret`**:
  ```json
  {
    "GOOGLE_OAUTH_CLIENT_SECRET": "<secret-value>"
  }
  ```

- **`busyb/s3-credentials-bucket`** (plain string):
  ```
  s3://busyb-oauth-tokens-758888582357/
  ```

#### Action Items

⚠️ **CRITICAL - Manual Verification Required**:

1. **Verify Google OAuth Client ID**:
   - Someone with access to the Google Cloud Console should verify that the Client ID stored in AWS Secrets Manager (`359995978669-8tfgeen6d1eo89jvpv6tggto7vml22an.apps.googleusercontent.com`) matches the actual Google OAuth Client ID for the BusyB project.
   - Verify this Client ID is configured for the correct authorized redirect URIs (will be set up in Phase 3).

2. **Verify Google OAuth Client Secret**:
   - Verify the Client Secret stored in AWS Secrets Manager matches the secret from Google Cloud Console.
   - If the secret has been rotated since October 28, 2025, it needs to be updated in Secrets Manager.

3. **ECS Task Definition Adjustment**:
   - When creating the ECS task definition in Phase 4, note that the secrets are stored as JSON objects with keys.
   - The task definition should use `secrets` instead of `environment` variables and reference the JSON keys:
     ```json
     "secrets": [
       {
         "name": "GOOGLE_OAUTH_CLIENT_ID",
         "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx:GOOGLE_OAUTH_CLIENT_ID::"
       },
       {
         "name": "GOOGLE_OAUTH_CLIENT_SECRET",
         "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z:GOOGLE_OAUTH_CLIENT_SECRET::"
       },
       {
         "name": "GOOGLE_MCP_CREDENTIALS_DIR",
         "valueFrom": "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM"
       }
     ]
     ```

#### Recommendations

1. **Secret Rotation**: Consider setting up automatic secret rotation for the Google OAuth credentials using AWS Secrets Manager rotation lambdas.

2. **Secret Versioning**: The Google OAuth secrets were created on 2025-10-28. If these credentials have been rotated since then, they should be updated.

3. **Documentation**: Update Phase 4 task definition template to reflect the correct JSON key structure for the secrets.

---

## Notes for Future Phases

### Task 1.7: Test AWS Credentials and Permissions

**Status**: ✅ COMPLETE

#### Test Results Summary

All AWS credentials and permissions tests **PASSED**. No issues found.

| Test Category | Tests | Status | Details |
|--------------|-------|--------|---------|
| ECR Access | 1 | ✅ All Pass | Repository accessible |
| Secrets Manager | 3 | ✅ All Pass | All 3 secrets readable |
| S3 Operations | 3 | ✅ All Pass | List, write, delete verified |
| CloudWatch Logs | 1 | ✅ All Pass | Log group accessible |
| ECS Cluster | 1 | ✅ All Pass | Cluster active |
| IAM Roles | 3 | ✅ All Pass | Both roles verified with correct policies |
| **TOTAL** | **12** | ✅ **All Pass** | Zero permission errors |

#### Key Findings

1. **Secret Format Confirmation**: Google OAuth secrets are JSON objects (not plain strings):
   - Must use JSON key notation in ECS task definition: `:GOOGLE_OAUTH_CLIENT_ID::`
   - Already documented in Task 1.3 action items

2. **S3 Permissions Complete**: All S3 operations verified working:
   - ListBucket ✅
   - GetObject ✅
   - PutObject ✅
   - DeleteObject ✅

3. **IAM Roles Correct**:
   - ecsTaskExecutionRole has AmazonECSTaskExecutionRolePolicy + SecretsManagerReadWrite
   - busyb-google-workspace-mcp-task-role has inline policy with S3 + Secrets Manager permissions
   - Both have correct trust relationships

#### Test Artifacts

- 📄 **Detailed Results**: `plan_cicd/aws_credentials_test_results.md`
- 🔧 **Test Script**: `plan_cicd/test_aws_credentials.sh` (executable, can be re-run anytime)
- 📋 **Infrastructure Update**: Test results added to `infrastructure_inventory.md`

#### No Action Items Required

All AWS resources and permissions are correctly configured. No remediation needed.

---

### Phase 2: Dockerfile Review & Optimization
- No action items yet

### Phase 3: ECS Infrastructure (Task Definition, Target Group, Service)
- Need to configure ALB routing rule for `/mcp/google*` path
- Need to verify health check endpoint `/health` is accessible

### Task 1.4: Configure GitHub Actions Secrets

**Status**: ⚠️ REQUIRES MANUAL ACTION

#### Overview

GitHub Actions secrets cannot be added programmatically via CLI without a GitHub personal access token. These secrets must be added manually through the GitHub web interface.

#### Required Secrets

The following secrets must be added to the GitHub repository (`Settings > Secrets and variables > Actions`):

| Secret Name | Value | Source |
|-------------|-------|--------|
| `AWS_REGION` | `us-east-1` | Infrastructure inventory |
| `AWS_ACCOUNT_ID` | `758888582357` | Infrastructure inventory |
| `AWS_ACCESS_KEY_ID` | `<from IAM user>` | Created in setup process |
| `AWS_SECRET_ACCESS_KEY` | `<from IAM user>` | Created in setup process |
| `ECS_CLUSTER` | `busyb-cluster` | Infrastructure inventory |
| `ECS_SERVICE_GOOGLE_WORKSPACE` | `busyb-google-workspace-mcp-service` | Infrastructure inventory |

#### Action Items

⚠️ **MANUAL ACTION REQUIRED**:

1. **Create IAM User for GitHub Actions**:
   - IAM user name: `github-actions-google-workspace-mcp`
   - Create access key and save the `AccessKeyId` and `SecretAccessKey`
   - Attach policy with ECR and ECS permissions (see `github_secrets_setup.md` for full policy)

2. **Add Secrets to GitHub**:
   - Navigate to GitHub repository settings
   - Go to `Settings > Secrets and variables > Actions`
   - Add all 6 secrets listed above
   - Use the detailed guide in `plan_cicd/github_secrets_setup.md`

3. **Verify IAM Permissions**:
   - ECR permissions: `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`
   - ECS permissions: `ecs:UpdateService`, `ecs:DescribeServices`, `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`
   - IAM permissions: `iam:PassRole` (with condition for `ecs-tasks.amazonaws.com`)

4. **Security Considerations**:
   - Set calendar reminder to rotate access keys every 90 days
   - Enable CloudTrail logging for IAM user activity
   - Review GitHub repository collaborators who can access secrets
   - Follow principle of least privilege (policy only grants minimum required permissions)

#### Documentation

Comprehensive setup guide available at: `plan_cicd/github_secrets_setup.md`

This guide includes:
- Step-by-step IAM user creation
- Complete IAM policy JSON
- Screenshot-equivalent instructions for GitHub web interface
- Troubleshooting guide
- Security best practices
- Verification checklist

---

### Phase 4: GitHub Actions CI/CD
- Ensure GitHub Actions workflow uses the correct secret ARNs documented above
- Update task definition template with correct secret references
- Verify GitHub secrets are configured (see Task 1.4 above)

### Phase 5: Testing & Validation
- Test OAuth flow end-to-end with actual Google credentials
- Verify credential storage in S3 bucket works correctly

---

## Security Reminders

1. **Never commit secret ARNs with actual secret values** to version control
2. **Limit IAM permissions** to only those users/roles that need access to these secrets
3. **Enable CloudTrail logging** for Secrets Manager to audit secret access
4. **Rotate secrets regularly** - Google OAuth secrets should be rotated every 90 days
5. **Use IAM policies** to restrict which ECS tasks can access which secrets

---

## Contact Information

For questions about:
- **AWS Infrastructure**: Contact AWS administrator
- **Google OAuth Credentials**: Contact Google Cloud Console administrator
- **Deployment Process**: Refer to `plan_cicd/README.md`
