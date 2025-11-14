#!/bin/bash
# AWS Credentials Test Script
# Tests all AWS resources and permissions for Google Workspace MCP deployment
# Usage: ./test_aws_credentials.sh

set -e

echo "=========================================="
echo "AWS Credentials and Permissions Test"
echo "Google Workspace MCP Deployment"
echo "=========================================="
echo ""

# Color codes for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Test function
test_command() {
    local test_name="$1"
    local test_command="$2"

    echo -n "Testing: $test_name... "

    if eval "$test_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "1. ECR Repository Access"
test_command "ECR repository access" \
    "aws ecr describe-repositories --repository-names busyb-google-workspace-mcp --region us-east-1 --query 'repositories[0].repositoryUri'"
echo ""

echo "2. AWS Secrets Manager Access"
test_command "Google OAuth Client ID secret" \
    "aws secretsmanager get-secret-value --secret-id busyb/google-oauth-client-id --region us-east-1 --query 'ARN'"
test_command "Google OAuth Client Secret secret" \
    "aws secretsmanager get-secret-value --secret-id busyb/google-oauth-client-secret --region us-east-1 --query 'ARN'"
test_command "S3 Credentials Bucket secret" \
    "aws secretsmanager get-secret-value --secret-id busyb/s3-credentials-bucket --region us-east-1 --query 'SecretString'"
echo ""

echo "3. S3 Bucket Access"
test_command "S3 bucket list operation" \
    "aws s3 ls s3://busyb-oauth-tokens-758888582357/"

echo -n "Testing: S3 write and delete operations... "
if echo "test-file-$$" > /tmp/test-cred-$$.json && \
   aws s3 cp /tmp/test-cred-$$.json s3://busyb-oauth-tokens-758888582357/test-cred-$$.json > /dev/null 2>&1 && \
   aws s3 rm s3://busyb-oauth-tokens-758888582357/test-cred-$$.json > /dev/null 2>&1 && \
   rm /tmp/test-cred-$$.json; then
    echo -e "${GREEN}✅ PASS${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}❌ FAIL${NC}"
    ((TESTS_FAILED++))
    rm -f /tmp/test-cred-$$.json 2>/dev/null || true
fi
echo ""

echo "4. CloudWatch Logs Access"
test_command "CloudWatch log group access" \
    "aws logs describe-log-groups --log-group-name-prefix /ecs/busyb-google-workspace-mcp --region us-east-1 --query 'logGroups[0].logGroupName'"
echo ""

echo "5. ECS Cluster Access"
test_command "ECS cluster access" \
    "aws ecs describe-clusters --clusters busyb-cluster --region us-east-1 --query 'clusters[0].status'"
echo ""

echo "6. IAM Role Verification"
test_command "ECS Task Execution Role" \
    "aws iam get-role --role-name ecsTaskExecutionRole --query 'Role.RoleName'"
test_command "Google Workspace MCP Task Role" \
    "aws iam get-role --role-name busyb-google-workspace-mcp-task-role --query 'Role.RoleName'"
test_command "Task role inline policy" \
    "aws iam get-role-policy --role-name busyb-google-workspace-mcp-task-role --policy-name busyb-google-workspace-mcp-policy --query 'PolicyName'"
echo ""

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "All AWS credentials and permissions are working correctly."
    echo "You can proceed with the deployment."
    exit 0
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    echo ""
    echo "Please review the failed tests and check:"
    echo "1. AWS credentials are configured correctly"
    echo "2. IAM permissions are set up properly"
    echo "3. Resources exist in the correct region (us-east-1)"
    echo ""
    echo "For detailed information, see: plan_cicd/aws_credentials_test_results.md"
    exit 1
fi
