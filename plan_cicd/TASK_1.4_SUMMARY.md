# Task 1.4: Configure GitHub Actions Secrets - Summary

**Date Completed**: 2025-11-12
**Task Status**: ✅ Documentation Complete (Manual Action Required)

---

## What Was Done

Task 1.4 involved documenting the GitHub Actions secrets that need to be added to the repository for CI/CD deployment. Since GitHub Actions secrets cannot be added programmatically via CLI (without a GitHub personal access token), this task focused on creating comprehensive documentation and reference materials.

### Deliverables Created

1. **`github_secrets_setup.md`** - Complete setup guide (9 sections, ~500 lines)
   - Step-by-step IAM user creation instructions
   - Complete IAM policy JSON for GitHub Actions
   - Detailed GitHub web interface instructions
   - Troubleshooting guide
   - Security best practices
   - Verification checklist

2. **`github_secrets_values.md`** - Quick reference card
   - Copy-paste ready secret values
   - IAM user creation commands
   - Workflow usage examples
   - Key rotation process

3. **Updated `deployment_action_items.md`**
   - Added Task 1.4 as a manual action item
   - Listed all required secrets
   - Documented action items and security considerations

4. **Updated `infrastructure_inventory.md`**
   - Added GitHub Actions IAM user documentation
   - Documented IAM policy requirements
   - Listed resource ARNs that the user can access

5. **Updated `phase_1.md`**
   - Marked Task 1.4 as complete in the checklist

---

## GitHub Secrets Required

The following 6 secrets must be added to GitHub manually:

| Secret Name | Value | Type |
|-------------|-------|------|
| `AWS_REGION` | `us-east-1` | Configuration |
| `AWS_ACCOUNT_ID` | `758888582357` | Configuration |
| `AWS_ACCESS_KEY_ID` | From IAM user creation | Credential |
| `AWS_SECRET_ACCESS_KEY` | From IAM user creation | Credential |
| `ECS_CLUSTER` | `busyb-cluster` | Configuration |
| `ECS_SERVICE_GOOGLE_WORKSPACE` | `busyb-google-workspace-mcp-service` | Configuration |

---

## IAM User Setup

### User Details
- **IAM User Name**: `github-actions-google-workspace-mcp`
- **Purpose**: CI/CD deployment via GitHub Actions
- **Access Type**: Programmatic access only (no console access)

### IAM Policy
- **Policy Name**: `GitHubActionsGoogleWorkspaceMCPPolicy`
- **Permissions**:
  - ECR: Push Docker images
  - ECS: Register task definitions, update service
  - IAM: Pass role to ECS tasks (restricted)

### Security Features
- **Principle of Least Privilege**: Only grants minimum required permissions
- **Resource Restrictions**: Can only access specific ECR repo, ECS service, and IAM roles
- **No Delete Permissions**: Cannot delete infrastructure
- **No Secrets Access**: Cannot access AWS Secrets Manager or S3 directly
- **Conditional IAM PassRole**: Can only pass roles to `ecs-tasks.amazonaws.com`

---

## What Needs to Be Done Manually

### Step 1: Create IAM User (AWS CLI)

```bash
# Set user name
export IAM_USER_NAME="github-actions-google-workspace-mcp"

# Create user
aws iam create-user \
  --user-name ${IAM_USER_NAME} \
  --tags Key=Purpose,Value=GitHubActions Key=Service,Value=GoogleWorkspaceMCP

# Create access key (SAVE THE OUTPUT!)
aws iam create-access-key --user-name ${IAM_USER_NAME}

# Create policy (see github_secrets_setup.md for JSON)
aws iam create-policy \
  --policy-name GitHubActionsGoogleWorkspaceMCPPolicy \
  --policy-document file://github-actions-policy.json

# Attach policy
aws iam attach-user-policy \
  --user-name ${IAM_USER_NAME} \
  --policy-arn arn:aws:iam::758888582357:policy/GitHubActionsGoogleWorkspaceMCPPolicy
```

### Step 2: Add Secrets to GitHub (Web Interface)

1. Navigate to: `https://github.com/YOUR_ORG/google_workspace_mcp/settings/secrets/actions`
2. Click "New repository secret"
3. Add each of the 6 secrets listed above
4. Use values from infrastructure_inventory.md and IAM user creation output

### Step 3: Verify Setup

- [ ] All 6 secrets visible in GitHub
- [ ] IAM user exists in AWS
- [ ] IAM policy attached to user
- [ ] Access key is active
- [ ] No typos in secret names (case-sensitive)

---

## IAM Permissions Breakdown

### ECR Permissions (Push Images)
```
ecr:GetAuthorizationToken         # Docker login
ecr:BatchCheckLayerAvailability   # Check if layers exist
ecr:GetDownloadUrlForLayer        # Download layer URLs
ecr:BatchGetImage                 # Get image manifests
ecr:PutImage                      # Push new images
ecr:InitiateLayerUpload           # Start layer upload
ecr:UploadLayerPart               # Upload layer parts
ecr:CompleteLayerUpload           # Finalize upload
```

### ECS Permissions (Deploy Service)
```
ecs:UpdateService                 # Trigger new deployment
ecs:DescribeServices              # Get service status
ecs:DescribeTaskDefinition        # Get task def details
ecs:RegisterTaskDefinition        # Register new task def revision
```

### IAM Permissions (Pass Roles)
```
iam:PassRole                      # Allow ECS to assume roles
Condition: iam:PassedToService = ecs-tasks.amazonaws.com
Resources:
  - arn:aws:iam::758888582357:role/ecsTaskExecutionRole
  - arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role
```

---

## Security Best Practices

### Access Key Rotation
- **Frequency**: Every 90 days
- **Process**: Create new key → Update GitHub → Test → Delete old key
- **Reminder**: Set calendar reminder for rotation

### Monitoring
- **CloudTrail**: Enable logging for IAM user API calls
- **Last Used**: Check access key last used date regularly
- **Failed Logins**: Monitor for authentication failures

### Access Control
- **GitHub Repository**: Only admins can manage secrets
- **IAM Policy**: Review permissions quarterly
- **Access Keys**: Max 2 active keys per user (rotate overlap)

---

## How Secrets Are Used in CI/CD

The GitHub Actions workflow will use these secrets as follows:

```yaml
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ secrets.AWS_REGION }}

- name: Login to Amazon ECR
  uses: aws-actions/amazon-ecr-login@v2

- name: Build and push Docker image
  run: |
    docker build -t $ECR_REPOSITORY:${{ github.sha }} .
    docker tag $ECR_REPOSITORY:${{ github.sha }} \
      ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:${{ github.sha }}
    docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:${{ github.sha }}

- name: Deploy to ECS
  run: |
    aws ecs update-service \
      --cluster ${{ secrets.ECS_CLUSTER }} \
      --service ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
      --force-new-deployment
```

---

## Verification Checklist

After completing the manual setup, verify:

- [ ] **IAM User Created**
  - User name: `github-actions-google-workspace-mcp`
  - Access type: Programmatic only
  - Access key created and saved

- [ ] **IAM Policy Attached**
  - Policy name: `GitHubActionsGoogleWorkspaceMCPPolicy`
  - Permissions verified (ECR, ECS, IAM PassRole)
  - Resources restricted to Google Workspace MCP only

- [ ] **GitHub Secrets Added**
  - AWS_REGION = `us-east-1`
  - AWS_ACCOUNT_ID = `758888582357`
  - AWS_ACCESS_KEY_ID = `<from IAM user>`
  - AWS_SECRET_ACCESS_KEY = `<from IAM user>`
  - ECS_CLUSTER = `busyb-cluster`
  - ECS_SERVICE_GOOGLE_WORKSPACE = `busyb-google-workspace-mcp-service`

- [ ] **Security Configured**
  - CloudTrail enabled
  - Calendar reminder set for key rotation (90 days)
  - Access key status: Active
  - GitHub repository collaborators reviewed

- [ ] **Documentation Updated**
  - infrastructure_inventory.md includes IAM user details
  - deployment_action_items.md includes manual action item
  - phase_1.md Task 1.4 marked as complete

---

## Related Files

### Setup Guides
- **Comprehensive Guide**: `plan_cicd/github_secrets_setup.md`
- **Quick Reference**: `plan_cicd/github_secrets_values.md`

### Project Documentation
- **Infrastructure Inventory**: `plan_cicd/infrastructure_inventory.md`
- **Action Items**: `plan_cicd/deployment_action_items.md`
- **Phase 1 Plan**: `plan_cicd/phase_1.md`

### Future Reference
- **Phase 4 (CI/CD)**: Will use these secrets in GitHub Actions workflow
- **IAM Policy File**: Create `github-actions-policy.json` with policy from `github_secrets_setup.md`

---

## Troubleshooting Reference

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Access Denied in workflow | IAM policy not attached | Verify policy attachment |
| Invalid credentials | Wrong secret values | Check for typos, no whitespace |
| Cannot pass role | Missing IAM PassRole | Verify IAM policy includes PassRole |
| Secret not found | Wrong secret name | Secret names are case-sensitive |
| Token expired | Inactive access key | Create new access key |

### Verification Commands

```bash
# Check IAM user exists
aws iam get-user --user-name github-actions-google-workspace-mcp

# List attached policies
aws iam list-attached-user-policies --user-name github-actions-google-workspace-mcp

# Check access key status
aws iam list-access-keys --user-name github-actions-google-workspace-mcp

# Test IAM permissions (should succeed)
aws ecr describe-repositories --repository-names busyb-google-workspace-mcp

# Test IAM permissions (should succeed)
aws ecs describe-services --cluster busyb-cluster --services busyb-google-workspace-mcp-service
```

---

## Next Steps

### Immediate Next Steps (Phase 1)
1. **Task 1.5**: Create CloudWatch Log Group (`/ecs/busyb-google-workspace-mcp`)
2. **Task 1.6**: Verify IAM Task Roles (create `busyb-google-workspace-mcp-task-role`)
3. **Task 1.7**: Test AWS Credentials and Permissions

### Future Dependencies (Phase 4)
- GitHub Actions workflow will be created in Phase 4
- Workflow will reference these secrets
- First workflow run will test that secrets are configured correctly
- Workflow will build Docker image, push to ECR, and deploy to ECS

---

## Summary

Task 1.4 is complete from a documentation perspective. The following deliverables were created:

✅ Comprehensive setup guide (github_secrets_setup.md)
✅ Quick reference card (github_secrets_values.md)
✅ IAM policy JSON documented
✅ GitHub secrets list documented
✅ Security best practices documented
✅ Troubleshooting guide created
✅ Verification checklist provided
✅ Infrastructure inventory updated
✅ Deployment action items updated
✅ Phase 1 checklist updated

**Manual Action Required**: Follow the instructions in `github_secrets_setup.md` to:
1. Create IAM user and access key
2. Attach IAM policy to user
3. Add secrets to GitHub repository
4. Verify setup is complete

Once the manual setup is done, proceed to Task 1.5: Create CloudWatch Log Group.
