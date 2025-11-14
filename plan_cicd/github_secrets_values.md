# GitHub Secrets - Quick Reference Values

**Last Updated**: 2025-11-12
**Repository**: google_workspace_mcp
**Purpose**: Quick reference for copy-pasting GitHub secret values

---

## ⚠️ Security Warning

This document contains configuration values that will be added to GitHub as secrets. While these are not sensitive credentials themselves, they reference production AWS infrastructure. Keep this document secure and do not commit it to public repositories.

---

## GitHub Secrets to Add

Copy these values when adding secrets to GitHub (`Settings > Secrets and variables > Actions`):

### 1. AWS_REGION
```
us-east-1
```

### 2. AWS_ACCOUNT_ID
```
758888582357
```

### 3. AWS_ACCESS_KEY_ID
```
<REPLACE_WITH_ACCESS_KEY_FROM_IAM_USER_CREATION>
```
**Format**: `AKIA...` (20 characters)
**Source**: Output from `aws iam create-access-key --user-name github-actions-google-workspace-mcp`

### 4. AWS_SECRET_ACCESS_KEY
```
<REPLACE_WITH_SECRET_KEY_FROM_IAM_USER_CREATION>
```
**Format**: Long string starting with lowercase letters (40 characters)
**Source**: Output from `aws iam create-access-key --user-name github-actions-google-workspace-mcp`
**Important**: Only shown once during creation. If lost, create a new access key.

### 5. ECS_CLUSTER
```
busyb-cluster
```

### 6. ECS_SERVICE_GOOGLE_WORKSPACE
```
busyb-google-workspace-mcp-service
```

---

## How to Add Secrets to GitHub

### Via Web Interface (Recommended)

1. Navigate to: `https://github.com/YOUR_ORG/google_workspace_mcp/settings/secrets/actions`
2. Click **"New repository secret"**
3. Enter the **Name** (e.g., `AWS_REGION`)
4. Enter the **Value** (copy from above)
5. Click **"Add secret"**
6. Repeat for all 6 secrets

### Verification

After adding all secrets, you should see 6 repository secrets listed in GitHub:

- ✅ AWS_REGION
- ✅ AWS_ACCOUNT_ID
- ✅ AWS_ACCESS_KEY_ID
- ✅ AWS_SECRET_ACCESS_KEY
- ✅ ECS_CLUSTER
- ✅ ECS_SERVICE_GOOGLE_WORKSPACE

---

## IAM User Creation Commands

Before adding secrets to GitHub, create the IAM user and access key:

### Step 1: Create IAM User

```bash
export IAM_USER_NAME="github-actions-google-workspace-mcp"

aws iam create-user \
  --user-name ${IAM_USER_NAME} \
  --tags Key=Purpose,Value=GitHubActions Key=Service,Value=GoogleWorkspaceMCP
```

### Step 2: Create Access Key

```bash
aws iam create-access-key --user-name ${IAM_USER_NAME}
```

**Save the output!** It will look like:

```json
{
    "AccessKey": {
        "UserName": "github-actions-google-workspace-mcp",
        "AccessKeyId": "AKIAIOSFODNN7EXAMPLE",
        "Status": "Active",
        "SecretAccessKey": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "CreateDate": "2025-11-12T10:30:00Z"
    }
}
```

Copy `AccessKeyId` → GitHub secret `AWS_ACCESS_KEY_ID`
Copy `SecretAccessKey` → GitHub secret `AWS_SECRET_ACCESS_KEY`

### Step 3: Attach IAM Policy

See `github_secrets_setup.md` for the complete IAM policy JSON. Then run:

```bash
aws iam create-policy \
  --policy-name GitHubActionsGoogleWorkspaceMCPPolicy \
  --policy-document file://github-actions-policy.json

aws iam attach-user-policy \
  --user-name ${IAM_USER_NAME} \
  --policy-arn arn:aws:iam::758888582357:policy/GitHubActionsGoogleWorkspaceMCPPolicy
```

---

## Validation Checklist

After adding secrets to GitHub, verify:

- [ ] All 6 secrets are visible in GitHub repository settings
- [ ] Secret names match exactly (case-sensitive)
- [ ] IAM user `github-actions-google-workspace-mcp` exists in AWS
- [ ] IAM user has policy `GitHubActionsGoogleWorkspaceMCPPolicy` attached
- [ ] Access key is active (Status: Active)
- [ ] Access key last used date will update after first workflow run
- [ ] Calendar reminder set for access key rotation in 90 days

---

## How These Secrets Are Used in GitHub Actions

The CI/CD workflow references these secrets as follows:

```yaml
name: Deploy Google Workspace MCP

on:
  push:
    branches: [ main ]

env:
  AWS_REGION: ${{ secrets.AWS_REGION }}
  ECR_REPOSITORY: busyb-google-workspace-mcp
  ECS_SERVICE: ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }}
  ECS_CLUSTER: ${{ secrets.ECS_CLUSTER }}
  ECS_TASK_DEFINITION: .aws/task-definition.json
  CONTAINER_NAME: busyb-google-workspace-mcp

jobs:
  deploy:
    name: Deploy
    runs-on: ubuntu-latest

    steps:
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ secrets.AWS_REGION }}

    - name: Login to Amazon ECR
      uses: aws-actions/amazon-ecr-login@v2

    - name: Build, tag, and push image to Amazon ECR
      run: |
        docker build -t $ECR_REPOSITORY:${{ github.sha }} .
        docker tag $ECR_REPOSITORY:${{ github.sha }} \
          ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/$ECR_REPOSITORY:${{ github.sha }}
        docker push ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.${{ secrets.AWS_REGION }}.amazonaws.com/$ECR_REPOSITORY:${{ github.sha }}

    - name: Deploy to Amazon ECS
      run: |
        aws ecs update-service \
          --cluster ${{ secrets.ECS_CLUSTER }} \
          --service ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
          --force-new-deployment
```

---

## Security Best Practices

### Access Key Rotation Schedule

Set calendar reminders for:

- **90 days from now**: Rotate GitHub Actions access key
- **Every 90 days**: Review IAM user permissions
- **Monthly**: Review GitHub Actions workflow runs for failures

### Key Rotation Process

When rotating access keys (every 90 days):

1. Create new access key:
   ```bash
   aws iam create-access-key --user-name github-actions-google-workspace-mcp
   ```

2. Update GitHub secrets with new values:
   - Update `AWS_ACCESS_KEY_ID`
   - Update `AWS_SECRET_ACCESS_KEY`

3. Test that new keys work (trigger a workflow run)

4. Delete old access key:
   ```bash
   aws iam delete-access-key \
     --user-name github-actions-google-workspace-mcp \
     --access-key-id <OLD_KEY_ID>
   ```

### Monitoring

Monitor IAM user activity:

```bash
# Check last used time
aws iam get-access-key-last-used --access-key-id <ACCESS_KEY_ID>

# List all access keys for user
aws iam list-access-keys --user-name github-actions-google-workspace-mcp

# View CloudTrail logs for user activity
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=Username,AttributeValue=github-actions-google-workspace-mcp \
  --max-results 50
```

---

## Troubleshooting

### Issue: Access key not found in IAM user creation output

**Solution**: The access key details are only shown once during creation. If you missed them:
1. Delete the access key if it was created
2. Create a new access key
3. Save the output immediately

### Issue: Cannot add secrets to GitHub repository

**Possible Causes**:
- Not enough permissions (need admin access)
- Repository is archived
- Organization policies restrict secret creation

**Solution**: Contact repository owner or GitHub organization admin.

### Issue: Workflow fails with "Invalid AWS credentials"

**Solution**:
1. Verify secrets are spelled correctly in GitHub (case-sensitive)
2. Check for extra whitespace in secret values
3. Verify access key is active in IAM
4. Create new access key and update secrets

---

## Reference Links

- Full setup guide: `plan_cicd/github_secrets_setup.md`
- Infrastructure inventory: `plan_cicd/infrastructure_inventory.md`
- Deployment action items: `plan_cicd/deployment_action_items.md`
- Phase 1 plan: `plan_cicd/phase_1.md`

---

## Next Steps

After adding these secrets to GitHub:

1. ✅ Mark Task 1.4 as complete in `phase_1.md`
2. ➡️ Proceed to Task 1.5: Create CloudWatch Log Group
3. ➡️ Continue with Task 1.6: Verify IAM Task Roles
4. ➡️ In Phase 4, test the GitHub Actions workflow with these secrets
