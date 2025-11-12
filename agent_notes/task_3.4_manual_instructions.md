# Task 3.4: Manual Testing Instructions

**IMPORTANT**: This document contains step-by-step instructions for completing Task 3.4 via GitHub UI.

## Current Status

✓ Feature branch created: `feature/github-actions-workflow-test`
✓ Workflow file committed and pushed
✓ README badge added and committed
✓ Branch ready for PR creation

## Manual Steps Required

### Step 1: Create Pull Request

1. Open your browser and navigate to:
   ```
   https://github.com/busyb-ai/google_workspace_mcp/pull/new/feature/github-actions-workflow-test
   ```

2. GitHub should auto-fill the PR form. Use these details:
   - **Title**: `Add GitHub Actions Deployment Workflow`
   - **Description**:
     ```
     This PR adds GitHub Actions workflow for automated deployment to AWS ECS.

     ## Changes
     - GitHub Actions workflow file for automated deployments
     - Workflow status badge in README
     - Manual trigger support via workflow_dispatch
     - Docker build, tag, and push to ECR
     - ECS service update and stability checks

     ## Testing Notes
     - Initial testing will focus on Docker build and ECR push steps
     - ECS deployment steps will fail (expected) until Phase 4 is complete
     - Full end-to-end testing will be done after ECS service is created

     ## Related
     - Phase 3 Task 3.4: Test Workflow with Manual Trigger
     - Closes part of CI/CD setup (plan_cicd/phase_3.md)
     ```

3. Review the changed files in the PR
4. Click "Create pull request"

### Step 2: Review and Merge PR

1. Review the PR changes one more time
2. If everything looks good, click "Merge pull request"
3. Choose "Squash and merge" or "Create a merge commit" (your preference)
4. Confirm the merge
5. Delete the feature branch after merge (GitHub will prompt)

### Step 3: Navigate to GitHub Actions

1. After merging, go to the Actions tab:
   ```
   https://github.com/busyb-ai/google_workspace_mcp/actions
   ```

2. You should see the workflow: "Deploy Google Workspace MCP to AWS ECS"

### Step 4: Manually Trigger Workflow

1. Click on "Deploy Google Workspace MCP to AWS ECS" workflow
2. You'll see a "Run workflow" button on the right side
3. Click "Run workflow"
4. A dropdown will appear:
   - Branch: Select `main`
   - Click the green "Run workflow" button
5. The workflow will start running

### Step 5: Monitor Workflow Execution

1. Click on the running workflow (it will have a yellow dot while running)
2. Click on the job: "Build and Deploy Google Workspace MCP"
3. Watch each step execute in real-time:

   **Expected to SUCCEED** ✓:
   - Checkout code
   - Configure AWS credentials
   - Login to Amazon ECR
   - Build, tag, and push Docker image

   **Expected to FAIL** ⚠️:
   - Update ECS service (service doesn't exist yet)
   - Wait for service stability (won't reach this step)

   **Will RUN** (due to `if: always()`):
   - Get deployment status

4. Click on each step to view detailed logs

### Step 6: Verify Docker Image in ECR

After the workflow completes (even if it fails at ECS steps), verify the Docker image was pushed:

1. **Via AWS Console**:
   - Go to ECR: https://console.aws.amazon.com/ecr/repositories
   - Select region: us-east-1
   - Find repository: `busyb-google-workspace-mcp`
   - You should see two new image tags:
     - `latest`
     - `<commit-sha>` (e.g., `fc8a695...`)

2. **Via AWS CLI**:
   ```bash
   aws ecr describe-images \
     --repository-name busyb-google-workspace-mcp \
     --region us-east-1
   ```

### Step 7: Document Results

After completing the manual test, create a note with:

1. Did the PR merge successfully?
2. Did the workflow appear in Actions tab?
3. Were you able to trigger it manually?
4. Which steps succeeded?
5. Which steps failed (expected)?
6. Are the images visible in ECR?

**Save your notes** - they'll be useful for Phase 4 testing.

## Expected Outcomes

### Success Indicators ✓

- [ ] PR created and merged successfully
- [ ] Workflow appears in Actions tab
- [ ] Manual trigger works
- [ ] Docker build completes without errors
- [ ] ECR login succeeds
- [ ] Both image tags pushed to ECR (latest + SHA)
- [ ] Images visible in ECR repository

### Expected Failures ⚠️

- [ ] ECS service update fails with "Service not found" error
- [ ] Workflow overall status shows as "Failed" (red X)

This is **completely expected** and correct at this stage!

## What This Test Validates

✓ GitHub Actions workflow is properly configured
✓ AWS credentials are working
✓ ECR authentication is working
✓ Docker build process is working
✓ Image tagging strategy is working
✓ ECR push is working
✓ Manual trigger mechanism is working

## What Can't Be Tested Yet

⏳ ECS service updates
⏳ Service stability checks
⏳ Full deployment process
⏳ Health checks
⏳ Zero-downtime deployments

These will be tested after Phase 4 (ECS Service Creation).

## After Phase 4 Completion

When Phase 4 is complete, re-run this workflow:

1. Go to Actions tab
2. Select "Deploy Google Workspace MCP to AWS ECS"
3. Click "Run workflow" again
4. This time **all steps should succeed** ✓

## Troubleshooting

### Workflow doesn't appear in Actions tab
- Ensure PR was merged to `main` branch
- Refresh the Actions page
- Check that workflow file is in `.github/workflows/` directory

### Can't trigger workflow manually
- Ensure you're on the `main` branch view
- Ensure you have write permissions to the repository
- Check that `workflow_dispatch:` is in the workflow file

### Docker build fails
- Check Dockerfile syntax
- Verify all files referenced in Dockerfile exist
- Review build logs for specific error

### ECR login fails
- Verify AWS credentials in GitHub secrets
- Check IAM permissions for ECR
- Verify AWS region is correct (us-east-1)

### ECR push fails
- Verify ECR repository exists: `busyb-google-workspace-mcp`
- Check IAM permissions for ECR push
- Verify image name and tags are correct

## Questions?

If you encounter any issues not covered here, refer to:
- Full task documentation: `agent_notes/task_3.4_workflow_testing.md`
- Phase 3 plan: `plan_cicd/phase_3.md`
- GitHub Actions logs (most detailed information)

## Next Steps After Manual Testing

1. Document your test results
2. Verify images are in ECR
3. Move on to Phase 4 (ECS Service Creation)
4. Re-test workflow after Phase 4 for full end-to-end validation
