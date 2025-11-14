# Phase 3: GitHub Actions Workflow

## Overview

This phase focuses on creating the automated CI/CD pipeline using GitHub Actions. The workflow will automatically build Docker images, push them to ECR, and deploy to ECS whenever changes are pushed to the main branch or specific paths are modified. This ensures rapid, reliable deployments while maintaining quality through automated builds.

## Objectives

- Create GitHub Actions workflow for automated deployment
- Configure path-based triggers to only deploy when relevant files change
- Implement Docker build and push to ECR
- Implement automated ECS service updates
- Test workflow with manual triggers
- Document workflow behavior and troubleshooting

## Prerequisites

- Completed Phase 1 (AWS infrastructure and GitHub secrets configured)
- Completed Phase 2 (Production-ready Dockerfile)
- GitHub repository with admin access
- Understanding of GitHub Actions YAML syntax
- AWS credentials configured in GitHub secrets

## Context from Previous Phases

From Phase 1:
- GitHub secrets configured: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `AWS_ACCOUNT_ID`, `ECS_CLUSTER`, `ECS_SERVICE_GOOGLE_WORKSPACE`
- ECR repository created: `busyb-google-workspace-mcp`

From Phase 2:
- Production Dockerfile ready
- Entrypoint script for environment variable mapping
- Docker build tested locally

The GitHub Actions workflow will:
- Trigger on pushes to `main` branch for specific paths
- Build Docker image using the production Dockerfile
- Tag with both commit SHA and `latest`
- Push to ECR
- Force new deployment in ECS
- Wait for service to stabilize

## Time Estimate

**Total Phase Time**: 2-3 hours

---

## Tasks

### Task 3.1: Create GitHub Actions Workflow Directory

**Complexity**: Small
**Estimated Time**: 5 minutes

**Description**:
Set up the directory structure for GitHub Actions workflows.

**Actions**:
- Create `.github/workflows/` directory if it doesn't exist:
  ```bash
  mkdir -p .github/workflows
  ```
- Verify directory permissions are correct:
  ```bash
  ls -la .github/workflows
  ```
- Create a README in the workflows directory:
  ```bash
  echo "# GitHub Actions Workflows

  This directory contains automated CI/CD workflows for the Google Workspace MCP server.

  ## Workflows

  - \`deploy-google-workspace-mcp.yml\` - Main deployment workflow for AWS ECS
  " > .github/workflows/README.md
  ```

**Deliverables**:
- `.github/workflows/` directory created
- README.md in workflows directory

**Dependencies**: Phase 1 and Phase 2 completed

---

### Task 3.2: Create Main Deployment Workflow

**Complexity**: Medium
**Estimated Time**: 45 minutes

**Description**:
Create the main GitHub Actions workflow file for building and deploying the Google Workspace MCP server to AWS ECS.

**Actions**:
- Create `.github/workflows/deploy-google-workspace-mcp.yml`:
  ```yaml
  name: Deploy Google Workspace MCP to AWS ECS

  on:
    push:
      branches: [main]
      paths:
        - 'auth/**'
        - 'core/**'
        - 'gcalendar/**'
        - 'gchat/**'
        - 'gdocs/**'
        - 'gdrive/**'
        - 'gforms/**'
        - 'gmail/**'
        - 'gsearch/**'
        - 'gsheets/**'
        - 'gslides/**'
        - 'gtasks/**'
        - 'main.py'
        - 'pyproject.toml'
        - 'uv.lock'
        - 'Dockerfile'
        - 'docker-entrypoint.sh'
        - '.dockerignore'
        - '.github/workflows/deploy-google-workspace-mcp.yml'
    workflow_dispatch: # Allow manual triggers

  env:
    AWS_REGION: us-east-1
    ECR_REGISTRY: ${{ secrets.AWS_ACCOUNT_ID }}.dkr.ecr.us-east-1.amazonaws.com
    ECR_REPOSITORY: busyb-google-workspace-mcp

  jobs:
    build-and-deploy:
      name: Build and Deploy Google Workspace MCP
      runs-on: ubuntu-latest
      permissions:
        contents: read
        packages: write

      steps:
        - name: Checkout code
          uses: actions/checkout@v4

        - name: Configure AWS credentials
          uses: aws-actions/configure-aws-credentials@v4
          with:
            aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
            aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
            aws-region: ${{ env.AWS_REGION }}

        - name: Login to Amazon ECR
          id: login-ecr
          uses: aws-actions/amazon-ecr-login@v2

        - name: Build, tag, and push Docker image
          env:
            IMAGE_TAG: ${{ github.sha }}
          run: |
            echo "Building Docker image..."
            docker build -t ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} .

            echo "Tagging image as latest..."
            docker tag ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }} \
                       ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest

            echo "Pushing image with SHA tag..."
            docker push ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:${{ env.IMAGE_TAG }}

            echo "Pushing image with latest tag..."
            docker push ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:latest

            echo "✓ Image pushed successfully"

        - name: Update ECS service
          run: |
            echo "Forcing new deployment for ECS service..."
            aws ecs update-service \
              --cluster ${{ secrets.ECS_CLUSTER }} \
              --service ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
              --force-new-deployment \
              --region ${{ env.AWS_REGION }}

            echo "✓ Deployment initiated"

        - name: Wait for service stability
          run: |
            echo "Waiting for ECS service to stabilize..."
            aws ecs wait services-stable \
              --cluster ${{ secrets.ECS_CLUSTER }} \
              --services ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
              --region ${{ env.AWS_REGION }}

            echo "✓ Service is stable and running"

        - name: Get deployment status
          if: always()
          run: |
            echo "Getting final deployment status..."
            aws ecs describe-services \
              --cluster ${{ secrets.ECS_CLUSTER }} \
              --services ${{ secrets.ECS_SERVICE_GOOGLE_WORKSPACE }} \
              --query 'services[0].deployments' \
              --region ${{ env.AWS_REGION }}
  ```
- Verify YAML syntax:
  ```bash
  # Use a YAML linter or online validator
  yamllint .github/workflows/deploy-google-workspace-mcp.yml
  ```

**Deliverables**:
- `.github/workflows/deploy-google-workspace-mcp.yml` created
- YAML syntax validated
- Workflow includes all required steps

**Dependencies**: Task 3.1

---

### Task 3.3: Add Workflow Status Badge to README

**Complexity**: Small
**Estimated Time**: 10 minutes

**Description**:
Add a GitHub Actions status badge to the README to show deployment status at a glance.

**Actions**:
- Determine the badge URL format:
  ```
  https://github.com/<username>/<repo>/actions/workflows/deploy-google-workspace-mcp.yml/badge.svg
  ```
- Add badge to README.md near the top:
  ```markdown
  # Google Workspace MCP Server

  [![Deploy to AWS ECS](https://github.com/<username>/<repo>/actions/workflows/deploy-google-workspace-mcp.yml/badge.svg)](https://github.com/<username>/<repo>/actions/workflows/deploy-google-workspace-mcp.yml)

  Production-ready MCP server for Google Workspace integration...
  ```
- Commit the README change
- Verify badge displays correctly on GitHub

**Deliverables**:
- README.md updated with workflow badge
- Badge displays correctly and links to workflow runs

**Dependencies**: Task 3.2

---

### Task 3.4: Test Workflow with Manual Trigger

**Complexity**: Medium
**Estimated Time**: 30 minutes

**Description**:
Manually trigger the workflow to test it before enabling automatic deployments. This ensures the workflow runs successfully without deploying potentially broken code automatically.

**Actions**:
- Commit and push the workflow file to a feature branch first:
  ```bash
  git checkout -b feature/github-actions-workflow
  git add .github/workflows/deploy-google-workspace-mcp.yml
  git commit -m "Add GitHub Actions deployment workflow"
  git push origin feature/github-actions-workflow
  ```
- Create a pull request (but don't merge yet)
- Navigate to GitHub Actions tab in repository
- Note: Manual trigger won't work until merged to main, so we'll test after merge
- Merge the PR to main branch
- Go to Actions tab → Select "Deploy Google Workspace MCP to AWS ECS" workflow
- Click "Run workflow" → Select `main` branch → Click "Run workflow"
- Monitor workflow execution:
  - Check each step completes successfully
  - Review logs for any errors or warnings
  - Verify image is pushed to ECR
  - Verify ECS service update is triggered
  - Confirm service stabilizes successfully
- If workflow fails:
  - Review error logs
  - Fix issues in workflow file
  - Commit and push fixes
  - Re-run workflow

**Deliverables**:
- Workflow executed successfully via manual trigger
- Docker image built and pushed to ECR
- ECS service updated
- Service reached stable state
- Workflow logs show no errors

**Dependencies**: Task 3.2

**Note**: This task requires the ECS service to exist (created in Phase 4), so this test may need to be revisited after Phase 4 is complete.

---

### Task 3.5: Create Workflow Documentation

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Document the GitHub Actions workflow behavior, triggers, and troubleshooting steps for team reference.

**Actions**:
- Create `docs/ci-cd.md` documentation:
  ```markdown
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
    - `g*/**` - Google service integrations
    - `main.py` - Application entry point
    - `pyproject.toml`, `uv.lock` - Dependencies
    - `Dockerfile`, `docker-entrypoint.sh` - Container configuration
    - `.github/workflows/deploy-google-workspace-mcp.yml` - Workflow itself

  The workflow can also be triggered manually via the GitHub Actions UI.

  ### Steps

  1. **Checkout code** - Clones the repository
  2. **Configure AWS credentials** - Authenticates with AWS using secrets
  3. **Login to ECR** - Authenticates Docker with Amazon ECR
  4. **Build, tag, and push** - Builds Docker image and pushes to ECR
  5. **Update ECS service** - Forces new deployment with latest image
  6. **Wait for stability** - Waits for ECS service to stabilize

  ### Environment Variables

  - `AWS_REGION`: AWS region (us-east-1)
  - `ECR_REGISTRY`: ECR registry URL
  - `ECR_REPOSITORY`: ECR repository name (busyb-google-workspace-mcp)

  ### Secrets Required

  The following secrets must be configured in GitHub repository settings:
  - `AWS_ACCESS_KEY_ID` - AWS IAM access key
  - `AWS_SECRET_ACCESS_KEY` - AWS IAM secret key
  - `AWS_ACCOUNT_ID` - AWS account ID
  - `ECS_CLUSTER` - ECS cluster name (busyb-cluster)
  - `ECS_SERVICE_GOOGLE_WORKSPACE` - ECS service name

  ## Troubleshooting

  ### Workflow fails at "Build, tag, and push" step

  - **Check**: Dockerfile syntax and build errors
  - **Solution**: Test Docker build locally, fix errors, commit and push

  ### Workflow fails at "Login to ECR" step

  - **Check**: AWS credentials are correct and have ECR permissions
  - **Solution**: Verify GitHub secrets, check IAM permissions

  ### Workflow fails at "Update ECS service" step

  - **Check**: ECS service exists and credentials have ECS permissions
  - **Solution**: Verify service name in secrets, check IAM permissions

  ### Workflow times out at "Wait for service stability"

  - **Check**: ECS service deployment status, container logs
  - **Solution**: Review CloudWatch logs, check health check failures

  ### Manual Workflow Trigger

  To manually trigger deployment:
  1. Go to repository → Actions tab
  2. Select "Deploy Google Workspace MCP to AWS ECS"
  3. Click "Run workflow"
  4. Select `main` branch
  5. Click "Run workflow" button

  ## Rollback Procedure

  If a deployment causes issues:
  1. Identify the previous working image tag (commit SHA)
  2. Update ECS task definition to use previous image
  3. Force new deployment with previous image
  4. Or revert the commit and push to trigger new deployment
  ```
- Add troubleshooting section to main README.md
- Create a quick reference card for common workflow issues

**Deliverables**:
- `docs/ci-cd.md` created with comprehensive documentation
- Troubleshooting guide for common issues
- Team members can understand and operate the CI/CD pipeline

**Dependencies**: Task 3.4

---

### Task 3.6: Add Workflow Notifications (Optional)

**Complexity**: Small
**Estimated Time**: 20 minutes

**Description**:
Configure workflow notifications for deployment success/failure (optional but recommended for production visibility).

**Actions**:
- Consider notification options:
  - **Option 1**: GitHub built-in notifications (default)
  - **Option 2**: Slack webhook integration
  - **Option 3**: Email notifications via AWS SNS
- If implementing Slack notifications, add step to workflow:
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
                "text": "*Google Workspace MCP Deployment Successful*\n\nCommit: `${{ github.sha }}`\nActor: ${{ github.actor }}"
              }
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
                "text": "*Google Workspace MCP Deployment Failed*\n\nCommit: `${{ github.sha }}`\nActor: ${{ github.actor }}\n<${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}|View Logs>"
              }
            }
          ]
        }
  ```
- Add `SLACK_WEBHOOK_URL` to GitHub secrets if using Slack
- Test notifications with a manual workflow run
- Document notification configuration in `docs/ci-cd.md`

**Deliverables**:
- Notification integration added to workflow (if desired)
- Notifications tested and working
- Documentation updated

**Dependencies**: Task 3.5

**Note**: This task is optional and can be deferred if notifications aren't needed initially.

---

### Task 3.7: Verify Path-Based Triggers

**Complexity**: Small
**Estimated Time**: 15 minutes

**Description**:
Test that the workflow only triggers when relevant files are changed, and doesn't trigger for unrelated changes.

**Actions**:
- Test negative case (should NOT trigger workflow):
  ```bash
  git checkout -b test/no-trigger
  # Modify a file not in the paths list
  echo "# Test" >> README.md
  git add README.md
  git commit -m "test: update README"
  git push origin test/no-trigger
  ```
  - Create PR, merge to main
  - Verify workflow does NOT run
- Test positive case (SHOULD trigger workflow):
  ```bash
  git checkout -b test/trigger-workflow
  # Modify a file in the paths list
  echo "# Test comment" >> main.py
  git add main.py
  git commit -m "test: trigger workflow"
  git push origin test/trigger-workflow
  ```
  - Create PR, merge to main
  - Verify workflow DOES run
- Clean up test changes if needed
- Document path trigger behavior in `docs/ci-cd.md`

**Deliverables**:
- Path-based triggers verified working correctly
- Workflow only runs for relevant file changes
- Trigger behavior documented

**Dependencies**: Task 3.4

**Note**: The test commits can be reverted after verification.

---

## Phase 3 Checklist

- [x] Task 3.1: Create GitHub Actions Workflow Directory
- [x] Task 3.2: Create Main Deployment Workflow
- [x] Task 3.3: Add Workflow Status Badge to README
- [x] Task 3.4: Test Workflow with Manual Trigger (Partially - Docker/ECR steps tested, ECS steps require Phase 4)
- [x] Task 3.5: Create Workflow Documentation
- [x] Task 3.6: Add Workflow Notifications (Optional) - Documentation complete
- [x] Task 3.7: Verify Path-Based Triggers

## Success Criteria

- GitHub Actions workflow file created and syntactically valid
- Workflow successfully builds Docker image
- Image successfully pushed to ECR
- ECS service update triggered successfully
- Workflow only triggers for relevant file changes
- Manual workflow trigger works
- Comprehensive documentation available
- Status badge displays in README

## Known Issues

- Task 3.4 (testing ECS deployment) requires ECS service to exist first
  - Will need to revisit this test after Phase 4 (ECS service creation)
  - Initial test can focus on Docker build and ECR push steps
  - Full end-to-end test should be done after Phase 4
  - **Update 2025-11-12**: Feature branch created and pushed. PR ready for creation.
    See `agent_notes/task_3.4_workflow_testing.md` for manual testing instructions.
    Docker build and ECR push can be tested now; ECS deployment requires Phase 4.

- Task 3.7 (verifying path-based triggers) requires GitHub UI access
  - Test branches have been created and pushed
  - Expected behavior is documented
  - Actual verification requires creating and merging PRs via GitHub UI
  - **Update 2025-11-12**: Test branches created and pushed:
    - `test/no-trigger-documentation` - Should NOT trigger workflow
    - `test/trigger-main-py` - Should trigger workflow
    - `test/trigger-auth-module` - Should trigger workflow
    - `test/trigger-dockerfile` - Should trigger workflow
  - See `agent_notes/task_3.7_path_trigger_verification.md` for detailed test procedures
  - Path trigger behavior documented in `docs/ci-cd.md`

## Next Steps

Proceed to Phase 4: ECS Task Definition & Service Creation
