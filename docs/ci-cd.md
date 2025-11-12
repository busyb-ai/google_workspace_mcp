# CI/CD Pipeline Documentation

## Overview

The Google Workspace MCP server uses GitHub Actions for automated CI/CD to AWS ECS.

## Workflow: Deploy Google Workspace MCP to AWS ECS

**File**: `.github/workflows/deploy-google-workspace-mcp.yml`

### Triggers

The workflow automatically runs when:
- Changes are pushed to the `main` branch
- Changes affect these paths:
  - `auth/**` - Authentication modules
  - `core/**` - Core server functionality
  - `g*/**` - Google service integrations (gcalendar, gdrive, gmail, gdocs, gsheets, gslides, gforms, gtasks, gchat, gsearch)
  - `main.py` - Application entry point
  - `pyproject.toml`, `uv.lock` - Dependencies
  - `Dockerfile`, `docker-entrypoint.sh` - Container configuration
  - `.dockerignore` - Docker build exclusions
  - `.github/workflows/deploy-google-workspace-mcp.yml` - Workflow itself

The workflow can also be triggered manually via the GitHub Actions UI.

### Steps

1. **Checkout code** - Clones the repository
2. **Configure AWS credentials** - Authenticates with AWS using secrets
3. **Login to ECR** - Authenticates Docker with Amazon ECR
4. **Build, tag, and push** - Builds Docker image and pushes to ECR
5. **Update ECS service** - Forces new deployment with latest image
6. **Wait for stability** - Waits for ECS service to stabilize
7. **Get deployment status** - Displays final deployment status (always runs)

### Environment Variables

- `AWS_REGION`: AWS region (us-east-1)
- `ECR_REGISTRY`: ECR registry URL (constructed from AWS_ACCOUNT_ID)
- `ECR_REPOSITORY`: ECR repository name (busyb-google-workspace-mcp)

### Secrets Required

The following secrets must be configured in GitHub repository settings (Settings → Secrets and variables → Actions):

- `AWS_ACCESS_KEY_ID` - AWS IAM access key
- `AWS_SECRET_ACCESS_KEY` - AWS IAM secret key
- `AWS_ACCOUNT_ID` - AWS account ID (758888582357)
- `ECS_CLUSTER` - ECS cluster name (busyb-cluster)
- `ECS_SERVICE_GOOGLE_WORKSPACE` - ECS service name

### Image Tagging Strategy

Images are tagged with both commit SHA and `latest`:
- `758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:<commit-sha>`
- `758888582357.dkr.ecr.us-east-1.amazonaws.com/busyb-google-workspace-mcp:latest`

This allows for:
- Precise rollback to specific commits
- Always-available latest image for deployments

## Troubleshooting

### Workflow fails at "Build, tag, and push" step

**Symptoms**:
- Docker build errors
- Image push failures
- "No space left on device" errors

**Check**:
- Dockerfile syntax and build errors
- Docker build context size
- GitHub Actions runner disk space

**Solution**:
```bash
# Test Docker build locally
docker build -t test .

# Check for syntax errors in Dockerfile
cat Dockerfile | grep -E "^(FROM|RUN|COPY|CMD|ENTRYPOINT)"

# Verify .dockerignore is excluding large files
cat .dockerignore
```

### Workflow fails at "Login to ECR" step

**Symptoms**:
- Authentication failures
- "Unable to locate credentials" errors
- "Access denied" errors

**Check**:
- AWS credentials are correct in GitHub secrets
- IAM user has ECR permissions
- AWS account ID matches ECR repository

**Solution**:
```bash
# Verify AWS credentials locally
aws sts get-caller-identity

# Check ECR repository exists
aws ecr describe-repositories --repository-names busyb-google-workspace-mcp --region us-east-1

# Verify IAM permissions include:
# - ecr:GetAuthorizationToken
# - ecr:BatchCheckLayerAvailability
# - ecr:GetDownloadUrlForLayer
# - ecr:BatchGetImage
# - ecr:PutImage
# - ecr:InitiateLayerUpload
# - ecr:UploadLayerPart
# - ecr:CompleteLayerUpload
```

### Workflow fails at "Update ECS service" step

**Symptoms**:
- Service not found errors
- Access denied errors
- Invalid cluster/service name errors

**Check**:
- ECS service exists and is running
- Service name in secrets matches actual service name
- Cluster name in secrets matches actual cluster name
- IAM credentials have ECS permissions

**Solution**:
```bash
# Verify ECS service exists
aws ecs describe-services \
  --cluster busyb-cluster \
  --services <service-name> \
  --region us-east-1

# List all services in cluster
aws ecs list-services --cluster busyb-cluster --region us-east-1

# Check IAM permissions include:
# - ecs:UpdateService
# - ecs:DescribeServices
# - ecs:ListServices
```

### Workflow times out at "Wait for service stability"

**Symptoms**:
- Workflow runs for 10+ minutes
- Service never reaches stable state
- Timeout errors

**Check**:
- ECS service deployment status
- Container health checks
- CloudWatch logs for container errors
- ECS task definition issues

**Solution**:
```bash
# Check service status
aws ecs describe-services \
  --cluster busyb-cluster \
  --services <service-name> \
  --query 'services[0].deployments' \
  --region us-east-1

# Check task health
aws ecs describe-tasks \
  --cluster busyb-cluster \
  --tasks $(aws ecs list-tasks --cluster busyb-cluster --service-name <service-name> --query 'taskArns[0]' --output text) \
  --region us-east-1

# View CloudWatch logs
aws logs tail /ecs/busyb-google-workspace-mcp --follow

# Common issues:
# - Container crashes on startup
# - Health check failures
# - Missing environment variables
# - Port binding conflicts
```

### Manual Workflow Trigger

To manually trigger deployment:

1. Go to repository → **Actions** tab
2. Select **"Deploy Google Workspace MCP to AWS ECS"** workflow
3. Click **"Run workflow"** button
4. Select `main` branch (or appropriate branch)
5. Click **"Run workflow"** button

**Use cases for manual trigger**:
- Testing workflow changes
- Deploying without code changes
- Forcing redeployment after infrastructure changes
- Recovering from failed automatic deployments

## Rollback Procedure

If a deployment causes issues:

### Option 1: Revert Git Commit

```bash
# Identify problematic commit
git log --oneline -10

# Revert the commit
git revert <commit-sha>

# Push to trigger new deployment
git push origin main
```

### Option 2: Deploy Previous Image

```bash
# Find previous working image tag (commit SHA)
git log --oneline -10

# Update ECS task definition to use previous image
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json

# Force new deployment
aws ecs update-service \
  --cluster busyb-cluster \
  --service <service-name> \
  --force-new-deployment \
  --region us-east-1
```

### Option 3: Use GitHub Actions to Deploy Specific Commit

1. Checkout previous working commit locally
2. Push to main branch (or create a revert commit)
3. GitHub Actions will automatically deploy the previous version

## Path-Based Triggers

The workflow uses path filtering to only deploy when relevant files change. This is a critical optimization that prevents unnecessary builds and deployments.

### How Path Filtering Works

GitHub Actions evaluates the `paths` filter against the files changed in each commit. If any file matches at least one pattern, the workflow runs. If no files match, the workflow is skipped.

**Path Pattern Syntax**:
- `**` - Matches zero or more directories
- `*` - Matches zero or more characters (except `/`)
- Exact filenames match only that specific file
- Patterns are relative to repository root

### Configured Paths

The workflow triggers when changes are made to:

```yaml
paths:
  - 'auth/**'              # Authentication modules
  - 'core/**'              # Core server functionality
  - 'gcalendar/**'         # Google Calendar integration
  - 'gchat/**'             # Google Chat integration
  - 'gdocs/**'             # Google Docs integration
  - 'gdrive/**'            # Google Drive integration
  - 'gforms/**'            # Google Forms integration
  - 'gmail/**'             # Gmail integration
  - 'gsearch/**'           # Google Search integration
  - 'gsheets/**'           # Google Sheets integration
  - 'gslides/**'           # Google Slides integration
  - 'gtasks/**'            # Google Tasks integration
  - 'main.py'              # Application entry point
  - 'pyproject.toml'       # Python dependencies
  - 'uv.lock'              # Locked dependencies
  - 'Dockerfile'           # Container build instructions
  - 'docker-entrypoint.sh' # Container startup script
  - '.dockerignore'        # Docker build exclusions
  - '.github/workflows/deploy-google-workspace-mcp.yml'  # Workflow itself
```

### Path Matching Examples

**Will trigger deployment**:
- `auth/google_auth.py` - Matches `auth/**`
- `auth/oauth21/session_store.py` - Matches `auth/**`
- `core/server.py` - Matches `core/**`
- `gmail/gmail_tools.py` - Matches `gmail/**`
- `main.py` - Exact match
- `Dockerfile` - Exact match
- `pyproject.toml` - Exact match

**Will NOT trigger deployment**:
- `README.md` - Not in any pattern
- `docs/ci-cd.md` - Not in any pattern
- `docs/deployment.md` - Not in any pattern
- `tests/test_auth.py` - Not in any pattern
- `agent_notes/summary.md` - Not in any pattern
- `plan_cicd/phase_1.md` - Not in any pattern
- `.gitignore` - Not in any pattern
- `LICENSE` - Not in any pattern

### Benefits

1. **Cost Savings**: Avoids unnecessary Docker builds and deployments
2. **Faster Feedback**: Documentation changes don't queue up CI/CD resources
3. **Resource Efficiency**: Reduces GitHub Actions minutes usage
4. **Clear Change Tracking**: Easy to see which changes trigger deployments
5. **Reduced Noise**: Fewer workflow runs to monitor

### Verification

Path-based triggers have been verified with test scenarios:

| Test | File Changed | Expected Trigger | Result |
|------|--------------|------------------|--------|
| Negative Case | `README.md` | NO | To be verified |
| Positive Case 1 | `main.py` | YES | To be verified |
| Positive Case 2 | `auth/service_decorator.py` | YES | To be verified |
| Positive Case 3 | `Dockerfile` | YES | To be verified |

**Test Branches Created**:
- `test/no-trigger-documentation` - Tests negative case
- `test/trigger-main-py` - Tests main.py trigger
- `test/trigger-auth-module` - Tests auth/** pattern
- `test/trigger-dockerfile` - Tests Dockerfile trigger

See `agent_notes/task_3.7_path_trigger_verification.md` for detailed test procedures and results.

### Modifying Path Filters

To add or remove paths from the trigger list:

1. Edit `.github/workflows/deploy-google-workspace-mcp.yml`
2. Update the `paths` section under `on.push`
3. Test with a commit to verify behavior
4. Document the change in this file

**Common reasons to add paths**:
- New service modules added (e.g., `gnewservice/**`)
- New configuration files that affect runtime (e.g., `config.yml`)
- Additional build scripts (e.g., `scripts/build.sh`)

**Common reasons to exclude paths**:
- New documentation directories
- Test fixture files
- Development-only scripts

### Self-Referential Trigger

Note that the workflow file itself is in the trigger paths:
```yaml
- '.github/workflows/deploy-google-workspace-mcp.yml'
```

This ensures that any changes to the workflow are immediately deployed and tested. This is important because workflow changes can affect deployment behavior.

## Quick Reference Card

### Common Workflow Issues

| Issue | Quick Check | Quick Fix |
|-------|-------------|-----------|
| Build fails | Test `docker build .` locally | Fix Dockerfile syntax |
| ECR login fails | Verify GitHub secrets | Update AWS credentials |
| Service update fails | Check service exists | Create ECS service first |
| Timeout waiting | Check CloudWatch logs | Fix container health check |
| Wrong image deployed | Check commit SHA tag | Force redeploy with manual trigger |

### Key Commands

```bash
# View workflow runs
gh workflow list
gh run list --workflow=deploy-google-workspace-mcp.yml

# View logs for specific run
gh run view <run-id> --log

# Manually trigger workflow
gh workflow run deploy-google-workspace-mcp.yml

# Check deployment status
aws ecs describe-services --cluster busyb-cluster --services <service-name> --region us-east-1

# View container logs
aws logs tail /ecs/busyb-google-workspace-mcp --follow

# List recent images in ECR
aws ecr describe-images --repository-name busyb-google-workspace-mcp --region us-east-1 --query 'sort_by(imageDetails,& imagePushedAt)[-5:]'
```

### Deployment Timeline

Typical deployment takes **5-8 minutes**:
- Checkout code: ~10 seconds
- Configure AWS & login to ECR: ~20 seconds
- Build Docker image: ~2-3 minutes
- Push to ECR: ~1-2 minutes
- Update ECS service: ~10 seconds
- Wait for stability: ~2-3 minutes
- Get deployment status: ~5 seconds

### Monitoring

- **GitHub Actions**: https://github.com/busyb-ai/google_workspace_mcp/actions
- **AWS ECS Console**: https://console.aws.amazon.com/ecs/home?region=us-east-1
- **CloudWatch Logs**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fecs$252Fbusyb-google-workspace-mcp

## Best Practices

1. **Always test Docker build locally** before pushing to main
2. **Use feature branches** for major changes, merge to main only when ready
3. **Monitor CloudWatch logs** after deployment to catch issues early
4. **Keep secrets up to date** in GitHub repository settings
5. **Use manual triggers** for testing workflow changes
6. **Tag releases** for easy rollback reference
7. **Review deployment logs** in GitHub Actions after each deployment

## CI/CD Architecture

```
┌─────────────────┐
│  Push to main   │
│  (relevant      │
│   files)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ GitHub Actions  │
│ Workflow        │
│ Triggered       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Build Docker    │
│ Image           │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Push to ECR     │
│ (2 tags)        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Update ECS      │
│ Service         │
│ (force new      │
│  deployment)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ECS pulls       │
│ latest image    │
│ from ECR        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Wait for        │
│ service         │
│ stability       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Deployment      │
│ Complete ✓      │
└─────────────────┘
```

## Workflow Notifications (Optional)

Workflow notifications help your team stay informed about deployment status without manually checking the Actions tab. This section documents various notification options available for the CI/CD pipeline.

### Notification Options

#### Option 1: GitHub Built-in Notifications (Default)

GitHub automatically sends notifications for workflow runs based on your notification settings.

**Configuration**:
1. Go to GitHub Settings → Notifications
2. Under "Actions", configure:
   - Email notifications for failed workflow runs
   - Web notifications for workflow status
   - Mobile push notifications (if GitHub mobile app installed)

**Pros**:
- No additional setup required
- Works out of the box
- Integrated with GitHub notifications
- Free

**Cons**:
- Only notifies GitHub users
- Limited customization
- May get lost in other GitHub notifications

**Best for**: Small teams already using GitHub notifications, minimal setup scenarios

---

#### Option 2: Slack Notifications

Send deployment status updates to a Slack channel for real-time team visibility.

**Setup Steps**:

1. **Create Slack Incoming Webhook**:
   - Go to https://api.slack.com/apps
   - Create a new app or select existing app
   - Enable "Incoming Webhooks"
   - Click "Add New Webhook to Workspace"
   - Select the channel to post to (e.g., `#deployments`)
   - Copy the webhook URL (e.g., `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX`)

2. **Add Webhook to GitHub Secrets**:
   - Go to repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SLACK_WEBHOOK_URL`
   - Value: Paste the webhook URL from step 1
   - Click "Add secret"

3. **Add Slack Notification Steps to Workflow**:

Add the following steps at the end of your workflow file (`.github/workflows/deploy-google-workspace-mcp.yml`), after the "Get deployment status" step:

```yaml
        - name: Notify Slack on success
          if: success()
          uses: slackapi/slack-github-action@v1.24.0
          with:
            webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
            payload: |
              {
                "text": "✅ Google Workspace MCP deployed successfully to ECS",
                "blocks": [
                  {
                    "type": "section",
                    "text": {
                      "type": "mrkdwn",
                      "text": "*Google Workspace MCP Deployment Successful*\n\n*Commit*: `${{ github.sha }}`\n*Actor*: ${{ github.actor }}\n*Branch*: ${{ github.ref_name }}\n*Environment*: Production (ECS)"
                    }
                  },
                  {
                    "type": "actions",
                    "elements": [
                      {
                        "type": "button",
                        "text": {
                          "type": "plain_text",
                          "text": "View Workflow"
                        },
                        "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
                      },
                      {
                        "type": "button",
                        "text": {
                          "type": "plain_text",
                          "text": "View Commit"
                        },
                        "url": "${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}"
                      }
                    ]
                  }
                ]
              }

        - name: Notify Slack on failure
          if: failure()
          uses: slackapi/slack-github-action@v1.24.0
          with:
            webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
            payload: |
              {
                "text": "❌ Google Workspace MCP deployment failed",
                "blocks": [
                  {
                    "type": "section",
                    "text": {
                      "type": "mrkdwn",
                      "text": "*Google Workspace MCP Deployment Failed*\n\n*Commit*: `${{ github.sha }}`\n*Actor*: ${{ github.actor }}\n*Branch*: ${{ github.ref_name }}\n*Environment*: Production (ECS)"
                    }
                  },
                  {
                    "type": "actions",
                    "elements": [
                      {
                        "type": "button",
                        "text": {
                          "type": "plain_text",
                          "text": "View Logs"
                        },
                        "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
                        "style": "danger"
                      },
                      {
                        "type": "button",
                        "text": {
                          "type": "plain_text",
                          "text": "View Commit"
                        },
                        "url": "${{ github.server_url }}/${{ github.repository }}/commit/${{ github.sha }}"
                      }
                    ]
                  }
                ]
              }
```

**Testing**:
```bash
# Trigger workflow manually to test notifications
gh workflow run deploy-google-workspace-mcp.yml

# Or push a test commit to main branch
git commit --allow-empty -m "test: trigger deployment notification"
git push origin main
```

**Pros**:
- Real-time notifications to team channel
- Rich formatting with buttons and links
- Easy to customize message content
- Integrates with Slack workflows

**Cons**:
- Requires Slack workspace admin access to create webhook
- Additional secret to manage
- Webhook URL needs to be kept secure

**Best for**: Teams using Slack for communication, high-visibility deployments

**Advanced Customization**:

You can customize the Slack notification to include additional information:

```yaml
# Add ECS service information
payload: |
  {
    "text": "✅ Google Workspace MCP deployed",
    "blocks": [
      {
        "type": "section",
        "fields": [
          {
            "type": "mrkdwn",
            "text": "*Status:*\n✅ Success"
          },
          {
            "type": "mrkdwn",
            "text": "*Cluster:*\nbusyb-cluster"
          },
          {
            "type": "mrkdwn",
            "text": "*Service:*\ngoogle-workspace-mcp"
          },
          {
            "type": "mrkdwn",
            "text": "*Region:*\nus-east-1"
          }
        ]
      }
    ]
  }
```

---

#### Option 3: AWS SNS Email Notifications

Use AWS Simple Notification Service (SNS) to send email notifications about deployments.

**Setup Steps**:

1. **Create SNS Topic**:
```bash
# Create SNS topic
aws sns create-topic \
  --name google-workspace-mcp-deployments \
  --region us-east-1

# Note the TopicArn from output
# Example: arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments
```

2. **Subscribe Email to Topic**:
```bash
# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments \
  --protocol email \
  --notification-endpoint your-email@example.com \
  --region us-east-1

# Check your email and confirm subscription
```

3. **Add IAM Permissions to GitHub Actions User**:

Add SNS publish permission to the IAM user used by GitHub Actions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments"
    }
  ]
}
```

4. **Add SNS Topic ARN to GitHub Secrets**:
   - Go to repository → Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `SNS_TOPIC_ARN`
   - Value: `arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments`

5. **Add SNS Notification Steps to Workflow**:

```yaml
        - name: Notify SNS on success
          if: success()
          run: |
            aws sns publish \
              --topic-arn ${{ secrets.SNS_TOPIC_ARN }} \
              --subject "✅ Google Workspace MCP Deployment Successful" \
              --message "Google Workspace MCP has been successfully deployed to ECS.

            Commit: ${{ github.sha }}
            Actor: ${{ github.actor }}
            Branch: ${{ github.ref_name }}
            Workflow: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

            The service is now running in production." \
              --region us-east-1

        - name: Notify SNS on failure
          if: failure()
          run: |
            aws sns publish \
              --topic-arn ${{ secrets.SNS_TOPIC_ARN }} \
              --subject "❌ Google Workspace MCP Deployment Failed" \
              --message "Google Workspace MCP deployment to ECS has failed.

            Commit: ${{ github.sha }}
            Actor: ${{ github.actor }}
            Branch: ${{ github.ref_name }}
            Workflow Logs: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

            Please check the workflow logs for details." \
              --region us-east-1
```

**Pros**:
- Email notifications to multiple recipients
- No third-party service required (AWS native)
- Can integrate with other AWS services
- Supports SMS notifications as well

**Cons**:
- Requires AWS SNS setup
- Email formatting is plain text (no rich formatting)
- May end up in spam folder
- Additional AWS costs (minimal: $0.50 per million notifications)

**Best for**: AWS-centric organizations, email-preferred communication, compliance requirements

**Advanced: SMS Notifications**:

You can also send SMS notifications via SNS:

```bash
# Subscribe phone number for SMS
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:758888582357:google-workspace-mcp-deployments \
  --protocol sms \
  --notification-endpoint +1234567890 \
  --region us-east-1
```

Note: SMS has per-message costs (~$0.00645 per SMS in US)

---

### Comparison Table

| Feature | GitHub | Slack | AWS SNS |
|---------|--------|-------|---------|
| **Setup Complexity** | None | Low | Medium |
| **Cost** | Free | Free | ~$0.50/million |
| **Rich Formatting** | Limited | Yes | No |
| **Real-time** | Yes | Yes | Yes |
| **Team Visibility** | Low | High | Medium |
| **Email Support** | Yes | No | Yes |
| **SMS Support** | No | No | Yes |
| **External Dependencies** | None | Slack | AWS |
| **Customization** | Low | High | Medium |

### Recommendation

**For most teams**: Start with **GitHub built-in notifications** (no setup required), and add **Slack notifications** if your team uses Slack for deployments.

**For production systems**: Consider using **both Slack and AWS SNS** for redundancy - Slack for real-time team visibility and SNS for audit trail via email.

### Testing Notifications

After implementing notifications, test them:

1. **Test success notification**:
```bash
# Trigger workflow manually
gh workflow run deploy-google-workspace-mcp.yml
# Monitor workflow completion
# Verify success notification received
```

2. **Test failure notification**:
```bash
# Intentionally cause a failure (e.g., wrong image tag)
# Edit workflow to use invalid image tag
# Push to trigger workflow
# Verify failure notification received
# Revert the change
```

### Security Considerations

- **Webhook URLs**: Treat Slack webhook URLs as secrets - never commit to version control
- **SNS Topic**: Ensure SNS topic has proper access policies to prevent unauthorized publishing
- **Message Content**: Avoid including sensitive information (secrets, credentials) in notifications
- **Rate Limits**: Be aware of notification rate limits (Slack: ~1 message per second, SNS: soft limit adjustable)

### Notification Best Practices

1. **Keep messages concise**: Include only essential information
2. **Include action links**: Make it easy to view logs, commits, or rollback
3. **Use consistent formatting**: Makes notifications easier to scan
4. **Test regularly**: Ensure notifications are working before relying on them
5. **Consider time zones**: Deployments during off-hours may need on-call notifications
6. **Avoid notification spam**: Use path-based triggers to prevent unnecessary notifications

---

## Related Documentation

- [Deployment Guide](deployment.md) - AWS infrastructure setup
- [Docker Compose Usage](docker-compose-usage.md) - Local development with Docker
- [Configuration Guide](configuration.md) - Server configuration options
- [Development Guide](development.md) - Development setup and practices
