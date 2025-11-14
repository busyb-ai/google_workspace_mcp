# Task 1.6: Verify IAM Task Roles - Summary

**Status**: ✅ COMPLETE
**Completed**: 2025-11-12
**Duration**: ~30 minutes

---

## Summary

Successfully verified the ECS Task Execution Role and created a new ECS Task Role for the Google Workspace MCP service with appropriate S3 and Secrets Manager permissions.

---

## Actions Completed

### 1. Verified ECS Task Execution Role

**Role Name**: `ecsTaskExecutionRole`
**Role ARN**: `arn:aws:iam::758888582357:role/ecsTaskExecutionRole`

**Verification Results**:
- ✅ Role exists and is active
- ✅ Has `AmazonECSTaskExecutionRolePolicy` attached (AWS managed)
- ✅ Has `SecretsManagerReadWrite` attached (AWS managed)
- ✅ Trust policy allows `ecs-tasks.amazonaws.com` to assume role
- ✅ Last used: 2025-11-12 (currently in use by other services)

**Purpose**: This role is used by ECS to pull container images from ECR and retrieve secrets from Secrets Manager during task startup.

### 2. Created Google Workspace MCP Task Role

**Role Name**: `busyb-google-workspace-mcp-task-role`
**Role ARN**: `arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role`
**Policy Name**: `busyb-google-workspace-mcp-policy`
**Created**: 2025-11-12

**Trust Policy**:
- Allows `ecs-tasks.amazonaws.com` to assume the role
- Standard ECS task role trust relationship

**Inline Policy Permissions**:
The role has the following permissions:

1. **S3 Object Operations** (on `arn:aws:s3:::busyb-oauth-tokens-758888582357/*`):
   - `s3:GetObject` - Read OAuth token files
   - `s3:PutObject` - Write OAuth token files
   - `s3:DeleteObject` - Delete OAuth token files

2. **S3 Bucket Operations** (on `arn:aws:s3:::busyb-oauth-tokens-758888582357`):
   - `s3:ListBucket` - List credential files in bucket

3. **Secrets Manager Access** (on `arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/*`):
   - `secretsmanager:GetSecretValue` - Read Google OAuth credentials

**Key Design Decisions**:
- Followed the existing pattern used by other MCP services (Jobber, QuickBooks, Research)
- Added `s3:ListBucket` permission (not present in other services) as required by Google Workspace MCP
- Used inline policy instead of managed policy (consistent with existing pattern)
- Separated S3 permissions into two statements:
  - Object-level operations apply to bucket contents (`/*`)
  - Bucket-level operations apply to bucket itself (no `/*`)

### 3. Created Policy Documents

Created the following files in `plan_cicd/`:

**task-role-policy.json** (inline policy document):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::busyb-oauth-tokens-758888582357/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::busyb-oauth-tokens-758888582357"
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/*"
      ]
    }
  ]
}
```

**task-role-trust-policy.json** (trust relationship document):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### 4. Updated Documentation

**infrastructure_inventory.md**:
- Added `busyb-google-workspace-mcp-task-role` to the task roles table
- Created new section documenting the Google Workspace MCP Task Role Policy
- Explained key differences from other MCP services
- Moved the task role from "To Be Created" to "Recently Created"
- Added `TASK_ROLE_ARN` environment variable to configuration values

**phase_1.md**:
- Marked Task 1.6 as complete in the Phase 1 Checklist

---

## Comparison with Existing Roles

### Similarities to Other MCP Task Roles
- Same trust policy (allows ECS tasks to assume role)
- S3 access to `busyb-oauth-tokens-758888582357` bucket
- Secrets Manager access to `busyb/*` secrets
- Inline policy instead of managed policy
- Similar naming convention

### Differences from Other MCP Task Roles
- **Added `s3:ListBucket` permission**: Required by Google Workspace MCP to list credential files
- **Separate statement for bucket operations**: Better aligns with AWS IAM best practices
  - Object operations (`GetObject`, `PutObject`, `DeleteObject`) use `bucket/*` ARN
  - Bucket operations (`ListBucket`) use `bucket` ARN (no `/*`)

---

## Files Created/Modified

### Created:
- `/Users/rob/Projects/busyb/google_workspace_mcp/plan_cicd/task-role-policy.json`
- `/Users/rob/Projects/busyb/google_workspace_mcp/plan_cicd/task-role-trust-policy.json`

### Modified:
- `/Users/rob/Projects/busyb/google_workspace_mcp/plan_cicd/infrastructure_inventory.md`
- `/Users/rob/Projects/busyb/google_workspace_mcp/plan_cicd/phase_1.md`

---

## Role ARNs for Reference

Use these ARNs in the ECS task definition (Phase 3):

```bash
# Task Execution Role (used by ECS to pull images and access secrets)
TASK_EXECUTION_ROLE_ARN="arn:aws:iam::758888582357:role/ecsTaskExecutionRole"

# Task Role (used by container to access S3 and Secrets Manager at runtime)
TASK_ROLE_ARN="arn:aws:iam::758888582357:role/busyb-google-workspace-mcp-task-role"
```

---

## Security Considerations

1. **Principle of Least Privilege**: The role only has permissions for:
   - Specific S3 bucket (`busyb-oauth-tokens-758888582357`)
   - Secrets under `busyb/*` namespace
   - No wildcard permissions

2. **Scope Limitations**:
   - S3 permissions limited to OAuth token bucket only
   - Cannot access other S3 buckets
   - Secrets Manager access limited to `busyb/*` namespace
   - Cannot modify IAM policies or create new resources

3. **Audit Trail**:
   - All S3 and Secrets Manager access will be logged in CloudTrail
   - Role usage tracked in IAM (last used timestamp)

4. **Future Enhancements** (if needed):
   - Consider adding S3 bucket versioning for credential history
   - Consider adding KMS key permissions if encryption keys change
   - Consider adding CloudWatch Logs permissions if application logging is needed

---

## Next Steps

The task role is now ready to be used in the ECS task definition (Phase 3).

**Proceed to**: Task 1.7 - Test AWS Credentials and Permissions

**After Phase 1**: Use this role ARN in the ECS task definition when creating the Google Workspace MCP service.

---

## Verification Commands

To verify the role and policy:

```bash
# Get role details
aws iam get-role --role-name busyb-google-workspace-mcp-task-role

# List policies attached to role
aws iam list-attached-role-policies --role-name busyb-google-workspace-mcp-task-role
aws iam list-role-policies --role-name busyb-google-workspace-mcp-task-role

# Get inline policy document
aws iam get-role-policy \
  --role-name busyb-google-workspace-mcp-task-role \
  --policy-name busyb-google-workspace-mcp-policy
```

---

## Success Criteria Met

✅ **ecsTaskExecutionRole verified** with correct permissions
✅ **busyb-google-workspace-mcp-task-role created** with S3 and Secrets Manager permissions
✅ **Role ARNs documented** in infrastructure_inventory.md
✅ **Policy document saved** as task-role-policy.json
✅ **Trust policy document saved** as task-role-trust-policy.json
✅ **Documentation updated** with complete role information
✅ **Phase 1 checklist updated** to mark task complete

---

**Task 1.6 Status**: ✅ COMPLETE
