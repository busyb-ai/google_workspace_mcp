# Task 5.2: OAuth Authentication Flow Testing

## Overview

This document provides comprehensive testing procedures for the Google Workspace MCP OAuth authentication flow, including both automated tests and manual verification steps.

## Test Environment

- **Service URL**: `http://google-workspace.busyb.local:8000`
- **External URL**: Available via ALB (if configured)
- **S3 Bucket**: `s3://busyb-oauth-tokens/google/`
- **CloudWatch Logs**: `/ecs/busyb-google-workspace-mcp`

## Prerequisites

- ECS service running and healthy
- Test Google account available
- AWS CLI configured with access to S3 and CloudWatch
- Service discovery working from Core Agent

## Test Cases

### Test 1: Direct OAuth Flow (via Service URL)

**Objective**: Test OAuth flow directly against the MCP service

**Steps**:

1. **Initiate OAuth Flow**
   ```bash
   # Request authorization URL
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "start_google_auth",
         "arguments": {
           "service_name": "gmail",
           "user_google_email": "test@gmail.com"
         }
       }
     }'
   ```

2. **Expected Response**
   ```json
   {
     "jsonrpc": "2.0",
     "id": 1,
     "result": {
       "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
       "message": "Please visit the authorization URL to complete authentication"
     }
   }
   ```

3. **Complete Authorization**
   - Copy authorization URL from response
   - Open URL in browser
   - Sign in with test Google account
   - Grant requested permissions
   - Browser should redirect to `http://localhost:8000/oauth2callback?code=...&state=...`
   - Should see success message

4. **Verify Credentials Stored**
   ```bash
   # Check S3 for credential file
   aws s3 ls s3://busyb-oauth-tokens/google/

   # Download and verify credential structure
   aws s3 cp s3://busyb-oauth-tokens/google/test@gmail.com.json - | python3 -m json.tool
   ```

5. **Expected Credential Structure**
   ```json
   {
     "token": "ya29.a0AfH6...",
     "refresh_token": "1//0gZ1...",
     "token_uri": "https://oauth2.googleapis.com/token",
     "client_id": "123456789-abc.apps.googleusercontent.com",
     "client_secret": "GOCSPX-...",
     "scopes": [
       "https://www.googleapis.com/auth/gmail.readonly",
       "https://www.googleapis.com/auth/userinfo.email",
       "openid"
     ],
     "expiry": "2025-01-20T10:30:00.000000Z"
   }
   ```

**Success Criteria**:
- ✅ Authorization URL returned successfully
- ✅ User can complete Google OAuth consent
- ✅ Callback processed without errors
- ✅ Credentials stored in S3 with correct structure
- ✅ All required fields present (token, refresh_token, scopes, expiry)

---

### Test 2: OAuth Flow via Core Agent

**Objective**: Test OAuth flow through Core Agent proxy

**Steps**:

1. **Request via Core Agent**
   ```bash
   # Core Agent should proxy to MCP service
   curl -X POST <CORE_AGENT_URL>/mcp/google-workspace \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "start_google_auth",
         "arguments": {
           "service_name": "drive",
           "user_google_email": "test@gmail.com"
         }
       }
     }'
   ```

2. **Follow Same Steps as Test 1**

3. **Verify Core Agent Logs**
   - Check Core Agent logs for proxy request
   - Verify successful communication with MCP service

**Success Criteria**:
- ✅ Core Agent successfully proxies request
- ✅ OAuth flow completes through proxy
- ✅ Credentials stored correctly

---

### Test 3: Token Refresh Flow

**Objective**: Verify automatic token refresh when tokens expire

**Steps**:

1. **Manually Expire Token**
   ```bash
   # Download current credential
   aws s3 cp s3://busyb-oauth-tokens/google/test@gmail.com.json /tmp/cred.json

   # Edit to set expired timestamp
   python3 << EOF
   import json
   from datetime import datetime, timedelta

   with open('/tmp/cred.json', 'r') as f:
       creds = json.load(f)

   # Set expiry to 1 hour ago
   creds['expiry'] = (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z'

   with open('/tmp/cred.json', 'w') as f:
       json.dump(creds, f, indent=2)

   print("Expiry set to:", creds['expiry'])
   EOF

   # Upload modified credential
   aws s3 cp /tmp/cred.json s3://busyb-oauth-tokens/google/test@gmail.com.json
   ```

2. **Make API Call to Trigger Refresh**
   ```bash
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "search_gmail_messages",
         "arguments": {
           "user_google_email": "test@gmail.com",
           "query": "subject:test"
         }
       }
     }'
   ```

3. **Monitor CloudWatch Logs**
   ```bash
   aws logs tail /ecs/busyb-google-workspace-mcp --follow --region us-east-1 | grep -i "refresh"
   ```

4. **Verify New Token**
   ```bash
   # Download credential again
   aws s3 cp s3://busyb-oauth-tokens/google/test@gmail.com.json - | python3 -m json.tool

   # Verify expiry is now in the future
   ```

**Success Criteria**:
- ✅ Service detects expired token
- ✅ Token refresh initiated automatically
- ✅ New token obtained from Google
- ✅ Updated credentials saved to S3
- ✅ Original API call succeeds after refresh
- ✅ No errors in CloudWatch logs

---

### Test 4: Multiple User Authentication

**Objective**: Verify multiple users can authenticate independently

**Steps**:

1. **Authenticate First User**
   ```bash
   # User 1: test@gmail.com
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "start_google_auth",
         "arguments": {
           "service_name": "gmail",
           "user_google_email": "user1@gmail.com"
         }
       }
     }'
   ```

2. **Authenticate Second User**
   ```bash
   # User 2: test2@gmail.com
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "start_google_auth",
         "arguments": {
           "service_name": "drive",
           "user_google_email": "user2@gmail.com"
         }
       }
     }'
   ```

3. **Verify Both Credentials Stored**
   ```bash
   aws s3 ls s3://busyb-oauth-tokens/google/
   # Should show:
   # user1@gmail.com.json
   # user2@gmail.com.json
   ```

4. **Test Both Users Can Access Their Services**
   ```bash
   # User 1 - Gmail
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "search_gmail_messages",
         "arguments": {
           "user_google_email": "user1@gmail.com",
           "query": "subject:test"
         }
       }
     }'

   # User 2 - Drive
   curl -X POST http://google-workspace.busyb.local:8000/mcp \
     -H "Content-Type: application/json" \
     -d '{
       "jsonrpc": "2.0",
       "id": 1,
       "method": "tools/call",
       "params": {
         "name": "list_drive_files",
         "arguments": {
           "user_google_email": "user2@gmail.com",
           "max_results": 10
         }
       }
     }'
   ```

**Success Criteria**:
- ✅ Multiple users can authenticate independently
- ✅ Each user's credentials stored separately in S3
- ✅ No cross-user credential leakage
- ✅ Each user can access their own resources

---

### Test 5: OAuth Error Handling

**Objective**: Verify proper error handling for OAuth failures

**Test 5.1: Invalid User Email**
```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "start_google_auth",
      "arguments": {
        "service_name": "gmail",
        "user_google_email": "invalid-email"
      }
    }
  }'
```

**Expected**: Error response with helpful message

**Test 5.2: Canceled Authorization**
1. Request authorization URL
2. Visit URL in browser
3. Click "Cancel" instead of granting permissions
4. Verify error handling

**Test 5.3: Revoked Credentials**
```bash
# Revoke credentials with Google
curl -X POST "https://oauth2.googleapis.com/revoke?token=<ACCESS_TOKEN>"

# Try to use service
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_gmail_messages",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "query": "subject:test"
      }
    }
  }'
```

**Expected**: Error indicating need to reauthenticate

**Success Criteria**:
- ✅ Proper error messages for invalid inputs
- ✅ Graceful handling of authorization cancellation
- ✅ Clear error when credentials revoked
- ✅ User prompted to reauthenticate when needed

---

### Test 6: S3 Credential Storage Security

**Objective**: Verify S3 credentials are stored securely

**Steps**:

1. **Check S3 Bucket Configuration**
   ```bash
   # Verify bucket encryption
   aws s3api get-bucket-encryption --bucket busyb-oauth-tokens

   # Verify public access blocked
   aws s3api get-public-access-block --bucket busyb-oauth-tokens
   ```

2. **Verify File Encryption**
   ```bash
   # Get object metadata
   aws s3api head-object \
     --bucket busyb-oauth-tokens \
     --key google/test@gmail.com.json
   ```

3. **Test IAM Permissions**
   ```bash
   # Verify only authorized roles can access
   # Try to access with different IAM role (should fail)
   ```

**Success Criteria**:
- ✅ Bucket encryption enabled (AES256 or KMS)
- ✅ Public access blocked
- ✅ Files encrypted at rest
- ✅ Only authorized IAM roles can access

---

## CloudWatch Log Analysis

### Key Log Messages to Look For

**Successful OAuth Flow**:
```
"Starting Google OAuth authentication"
"Authorization URL generated"
"OAuth callback received"
"Token exchange successful"
"Credentials stored in S3"
```

**Token Refresh**:
```
"Token expired, initiating refresh"
"Token refresh successful"
"Updated credentials stored in S3"
```

**Errors**:
```
"ERROR: OAuth authentication failed"
"ERROR: Token refresh failed"
"ERROR: S3 storage error"
```

### CloudWatch Insights Queries

**OAuth Success Rate (Last Hour)**:
```
fields @timestamp, @message
| filter @message like /OAuth/
| stats count(@message like /successful/) as success,
        count(@message like /failed/) as failures
| extend total = success + failures
| extend success_rate = success * 100 / total
```

**Token Refresh Activity**:
```
fields @timestamp, @message
| filter @message like /refresh/
| sort @timestamp desc
| limit 50
```

**OAuth Errors**:
```
fields @timestamp, @message
| filter @message like /OAuth/ and @message like /ERROR/
| sort @timestamp desc
| limit 100
```

---

## Troubleshooting Guide

### Issue: Authorization URL Not Generated

**Symptoms**: API call returns error instead of authorization URL

**Checks**:
1. Verify service is running: `curl http://google-workspace.busyb.local:8000/health`
2. Check CloudWatch logs for errors
3. Verify Google OAuth credentials in ECS environment variables
4. Verify required scopes defined in code

**Solution**: Check environment variables and Google Cloud Console configuration

---

### Issue: OAuth Callback Fails

**Symptoms**: Browser shows error after Google authorization

**Checks**:
1. Verify callback URL matches Google Cloud Console configuration
2. Check CloudWatch logs for callback processing errors
3. Verify state token validation
4. Check PKCE challenge validation

**Solution**: Update redirect URI in Google Cloud Console or fix server configuration

---

### Issue: Credentials Not Stored in S3

**Symptoms**: OAuth completes but no file in S3

**Checks**:
1. Verify ECS task role has S3 write permissions
2. Check CloudWatch logs for S3 errors
3. Verify S3 bucket name in environment variable
4. Check S3 bucket exists and is accessible

**Solution**: Update IAM policies or S3 configuration

---

### Issue: Token Refresh Fails

**Symptoms**: API calls fail with expired token error

**Checks**:
1. Verify refresh token present in credential file
2. Check if user revoked app access in Google account
3. Verify token exchange endpoint accessible
4. Check CloudWatch logs for refresh errors

**Solution**: Delete credential file and reauthenticate, or check Google OAuth client configuration

---

## Manual Test Checklist

- [ ] Direct OAuth flow completes successfully
- [ ] OAuth flow works through Core Agent
- [ ] Token refresh works automatically
- [ ] Multiple users can authenticate independently
- [ ] Error handling works for invalid inputs
- [ ] Error handling works for canceled authorization
- [ ] Error handling works for revoked credentials
- [ ] Credentials stored in S3 with correct structure
- [ ] S3 bucket properly secured
- [ ] CloudWatch logs show expected messages
- [ ] No sensitive data (tokens) logged
- [ ] Service handles concurrent OAuth requests
- [ ] Service survives restart with valid credentials

---

## Automated Test Script

```bash
#!/bin/bash
# oauth-test.sh - Automated OAuth flow testing

set -e

SERVICE_URL="http://google-workspace.busyb.local:8000"
TEST_EMAIL="test@gmail.com"
S3_BUCKET="busyb-oauth-tokens"

echo "=== OAuth Authentication Flow Test ==="
echo ""

# Test 1: Health check
echo "Test 1: Service health check"
curl -f -s ${SERVICE_URL}/health | python3 -m json.tool
echo "✅ Service is healthy"
echo ""

# Test 2: Request authorization URL
echo "Test 2: Request authorization URL"
RESPONSE=$(curl -s -X POST ${SERVICE_URL}/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "start_google_auth",
      "arguments": {
        "service_name": "gmail",
        "user_google_email": "'${TEST_EMAIL}'"
      }
    }
  }')

AUTH_URL=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['result']['authorization_url'])")
echo "Authorization URL: ${AUTH_URL}"
echo "✅ Authorization URL generated"
echo ""

# Manual step
echo "⏸️  MANUAL STEP REQUIRED:"
echo "1. Open this URL in browser: ${AUTH_URL}"
echo "2. Sign in and authorize the application"
echo "3. Wait for callback to complete"
echo "4. Press Enter when complete..."
read

# Test 3: Verify credentials in S3
echo "Test 3: Verify credentials in S3"
aws s3 ls s3://${S3_BUCKET}/google/${TEST_EMAIL}.json
echo "✅ Credential file exists in S3"
echo ""

# Test 4: Download and verify credential structure
echo "Test 4: Verify credential structure"
aws s3 cp s3://${S3_BUCKET}/google/${TEST_EMAIL}.json - | python3 -c "
import sys, json
creds = json.load(sys.stdin)
required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'scopes', 'expiry']
for field in required_fields:
    if field not in creds:
        print(f'❌ Missing required field: {field}')
        sys.exit(1)
print('✅ All required fields present')
print(f'   Token: {creds[\"token\"][:20]}...')
print(f'   Scopes: {len(creds[\"scopes\"])} scopes')
print(f'   Expiry: {creds[\"expiry\"]}')
"
echo ""

# Test 5: Use authenticated service
echo "Test 5: Test authenticated API call"
SEARCH_RESPONSE=$(curl -s -X POST ${SERVICE_URL}/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_gmail_messages",
      "arguments": {
        "user_google_email": "'${TEST_EMAIL}'",
        "query": "subject:test"
      }
    }
  }')

if echo "$SEARCH_RESPONSE" | grep -q '"result"'; then
  echo "✅ Authenticated API call successful"
else
  echo "❌ API call failed"
  echo "$SEARCH_RESPONSE"
  exit 1
fi
echo ""

echo "=== All OAuth Tests Passed! ==="
```

---

## Test Report Template

```markdown
# OAuth Authentication Flow Test Report

**Date**: YYYY-MM-DD
**Tester**: Name
**Service Version**: X.X.X
**Environment**: Production/Staging

## Test Summary

| Test Case | Status | Notes |
|-----------|--------|-------|
| Direct OAuth Flow | ✅ Pass | |
| OAuth via Core Agent | ✅ Pass | |
| Token Refresh | ✅ Pass | |
| Multiple Users | ✅ Pass | |
| Error Handling | ✅ Pass | |
| S3 Security | ✅ Pass | |

## Detailed Results

### Test 1: Direct OAuth Flow
- Authorization URL generated: ✅
- User consent completed: ✅
- Callback processed: ✅
- Credentials stored: ✅
- Time to complete: X seconds

### Test 2: OAuth via Core Agent
- Proxy request succeeded: ✅
- OAuth flow completed: ✅
- Time to complete: X seconds

[Continue for all tests...]

## Issues Found

1. **Issue Description**: [If any]
   - Severity: High/Medium/Low
   - Impact: [Description]
   - Workaround: [If applicable]
   - Fix required: Yes/No

## Recommendations

1. [Any recommendations for improvements]
2. [Performance optimizations]
3. [Security enhancements]

## Sign-off

- Tested by: [Name]
- Reviewed by: [Name]
- Approved for production: Yes/No
```

---

## Next Steps

After completing OAuth authentication testing:

1. ✅ Document all test results
2. ✅ Fix any issues found
3. ✅ Update deployment_action_items.md with critical findings
4. ➡️ Proceed to Task 5.3: Test Gmail Tools
5. ➡️ Continue with remaining Phase 5 tasks
