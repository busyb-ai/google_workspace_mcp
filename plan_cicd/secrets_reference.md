# AWS Secrets Manager - Quick Reference

**Last Updated**: 2025-11-12
**Project**: Google Workspace MCP Server

---

## Secret ARNs (for Copy-Paste)

### Google OAuth Client ID
```
arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx
```

### Google OAuth Client Secret
```
arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z
```

### S3 Credentials Bucket Path
```
arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM
```

---

## ECS Task Definition Snippet

Use this snippet in your ECS task definition (Phase 4):

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

**Important**: Note the `:GOOGLE_OAUTH_CLIENT_ID::` and `:GOOGLE_OAUTH_CLIENT_SECRET::` suffixes to extract values from JSON objects.

---

## IAM Policy Snippet

Use this in the Task Role policy (Task 1.6):

```json
{
  "Effect": "Allow",
  "Action": [
    "secretsmanager:GetSecretValue"
  ],
  "Resource": [
    "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-id-5AhKRx",
    "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/google-oauth-client-secret-mMQs8z",
    "arn:aws:secretsmanager:us-east-1:758888582357:secret:busyb/s3-credentials-bucket-Ba31ZM"
  ]
}
```

---

## AWS CLI Commands

### Get Secret Value
```bash
# Google OAuth Client ID
aws secretsmanager get-secret-value \
  --secret-id busyb/google-oauth-client-id \
  --region us-east-1 \
  --query 'SecretString' \
  --output text | jq -r '.GOOGLE_OAUTH_CLIENT_ID'

# Google OAuth Client Secret
aws secretsmanager get-secret-value \
  --secret-id busyb/google-oauth-client-secret \
  --region us-east-1 \
  --query 'SecretString' \
  --output text | jq -r '.GOOGLE_OAUTH_CLIENT_SECRET'

# S3 Credentials Bucket Path
aws secretsmanager get-secret-value \
  --secret-id busyb/s3-credentials-bucket \
  --region us-east-1 \
  --query 'SecretString' \
  --output text
```

### Update Secret Value
```bash
# Update Google OAuth Client ID
aws secretsmanager update-secret \
  --secret-id busyb/google-oauth-client-id \
  --secret-string '{"GOOGLE_OAUTH_CLIENT_ID":"NEW_VALUE"}' \
  --region us-east-1

# Update Google OAuth Client Secret
aws secretsmanager update-secret \
  --secret-id busyb/google-oauth-client-secret \
  --secret-string '{"GOOGLE_OAUTH_CLIENT_SECRET":"NEW_VALUE"}' \
  --region us-east-1

# Update S3 Credentials Bucket Path
aws secretsmanager update-secret \
  --secret-id busyb/s3-credentials-bucket \
  --secret-string "s3://busyb-oauth-tokens-758888582357/" \
  --region us-east-1
```

### Describe Secrets
```bash
# List all three secrets
aws secretsmanager list-secrets \
  --region us-east-1 \
  --filters Key=name,Values=busyb/google-oauth-client-id,busyb/google-oauth-client-secret,busyb/s3-credentials-bucket \
  --query 'SecretList[*].[Name,ARN]' \
  --output table
```

---

## Environment Variables (for local testing)

```bash
export GOOGLE_OAUTH_CLIENT_ID="359995978669-8tfgeen6d1eo89jvpv6tggto7vml22an.apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="<secret-from-secrets-manager>"
export GOOGLE_MCP_CREDENTIALS_DIR="s3://busyb-oauth-tokens-758888582357/"
```

---

## Notes

1. **Secret Format**: OAuth secrets are JSON objects with keys, S3 bucket is plain string
2. **JSON Key Extraction**: Use `:KEY_NAME::` suffix in ECS task definition to extract from JSON
3. **Security**: Never log or commit actual secret values
4. **Rotation**: Consider rotating Google OAuth credentials every 90 days
5. **Access**: Only ECS task execution role and authorized developers should have access
