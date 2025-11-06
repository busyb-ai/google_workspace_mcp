#!/usr/bin/env python3
"""
Manual S3 Storage Test Script - Task 5.2

This script tests the S3 storage functionality for Google OAuth credentials.
It can run with real AWS credentials or provide a test plan for manual verification.

Test Scenarios:
1. Test Save Credentials to S3
2. Test Load Credentials from S3
3. Test Find Any Credentials in S3 (single-user mode)
4. Test S3 Path Detection
5. Verify encryption is enabled
6. Verify file content is correct JSON

Usage:
    # Set environment variables
    export GOOGLE_MCP_CREDENTIALS_DIR=s3://test-workspace-mcp-credentials/
    export AWS_ACCESS_KEY_ID=your-key
    export AWS_SECRET_ACCESS_KEY=your-secret
    export AWS_REGION=us-east-1

    # Run tests
    python test_s3_storage_manual.py
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import S3 storage functions
from auth.s3_storage import (
    is_s3_path,
    parse_s3_path,
    get_s3_client,
    s3_file_exists,
    s3_upload_json,
    s3_download_json,
    s3_list_json_files,
    s3_delete_file
)


class S3TestResults:
    """Track test results"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []

    def record_pass(self, test_name: str, details: str = ""):
        self.passed.append((test_name, details))
        print(f"✅ PASS: {test_name}")
        if details:
            print(f"   {details}")

    def record_fail(self, test_name: str, error: str):
        self.failed.append((test_name, error))
        print(f"❌ FAIL: {test_name}")
        print(f"   Error: {error}")

    def record_skip(self, test_name: str, reason: str):
        self.skipped.append((test_name, reason))
        print(f"⏭️  SKIP: {test_name}")
        print(f"   Reason: {reason}")

    def summary(self) -> Dict[str, Any]:
        total = len(self.passed) + len(self.failed) + len(self.skipped)
        return {
            "total": total,
            "passed": len(self.passed),
            "failed": len(self.failed),
            "skipped": len(self.skipped),
            "pass_rate": f"{len(self.passed)/total*100:.1f}%" if total > 0 else "N/A"
        }


def test_s3_path_detection(results: S3TestResults):
    """Test Scenario 4: Test S3 Path Detection"""
    print("\n" + "="*60)
    print("Test Scenario 4: S3 Path Detection")
    print("="*60)

    test_cases = [
        ("s3://my-bucket/path/to/file.json", True, ("my-bucket", "path/to/file.json")),
        ("S3://my-bucket/credentials/", True, ("my-bucket", "credentials/")),
        ("/local/path/to/file.json", False, None),
        ("./relative/path", False, None),
        (None, False, None),
        ("", False, None),
        ("   ", False, None),
        ("s3://bucket-only", True, ("bucket-only", "")),
        ("s3://bucket//multiple///slashes//file.json", True, ("bucket", "multiple/slashes/file.json")),
    ]

    for path, expected_is_s3, expected_parse in test_cases:
        try:
            # Test is_s3_path()
            result = is_s3_path(path)
            if result == expected_is_s3:
                results.record_pass(
                    f"is_s3_path({repr(path)})",
                    f"Correctly returned {result}"
                )
            else:
                results.record_fail(
                    f"is_s3_path({repr(path)})",
                    f"Expected {expected_is_s3}, got {result}"
                )

            # Test parse_s3_path() for S3 paths
            if expected_is_s3 and expected_parse:
                try:
                    bucket, key = parse_s3_path(path)
                    if (bucket, key) == expected_parse:
                        results.record_pass(
                            f"parse_s3_path({repr(path)})",
                            f"Correctly parsed to ({bucket}, {key})"
                        )
                    else:
                        results.record_fail(
                            f"parse_s3_path({repr(path)})",
                            f"Expected {expected_parse}, got ({bucket}, {key})"
                        )
                except Exception as e:
                    results.record_fail(
                        f"parse_s3_path({repr(path)})",
                        str(e)
                    )
            elif not expected_is_s3:
                # Should raise ValueError for non-S3 paths
                try:
                    parse_s3_path(path)
                    results.record_fail(
                        f"parse_s3_path({repr(path)})",
                        "Should have raised ValueError for non-S3 path"
                    )
                except ValueError:
                    results.record_pass(
                        f"parse_s3_path({repr(path)})",
                        "Correctly raised ValueError for non-S3 path"
                    )

        except Exception as e:
            results.record_fail(f"S3 path test ({repr(path)})", str(e))


def check_aws_credentials() -> bool:
    """Check if AWS credentials are available"""
    # Check environment variables
    has_env_creds = bool(
        os.getenv('AWS_ACCESS_KEY_ID') and
        os.getenv('AWS_SECRET_ACCESS_KEY')
    )

    # Check for AWS credentials file
    aws_creds_file = os.path.expanduser('~/.aws/credentials')
    has_creds_file = os.path.exists(aws_creds_file)

    # Try to get S3 client (will work with IAM role on EC2/ECS)
    try:
        get_s3_client()
        return True
    except Exception:
        pass

    return has_env_creds or has_creds_file


def test_s3_save_credentials(results: S3TestResults, test_bucket: str):
    """Test Scenario 1: Test Save Credentials to S3"""
    print("\n" + "="*60)
    print("Test Scenario 1: Save Credentials to S3")
    print("="*60)

    test_email = "test-user@example.com"
    s3_path = f"{test_bucket}{test_email}.json"

    # Create test credential data
    test_credentials = {
        "token": "ya29.a0AfH6SMBtest123",
        "refresh_token": "1//0gZ1testrefresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test-client-id.apps.googleusercontent.com",
        "client_secret": "test-client-secret",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/drive.readonly"
        ],
        "expiry": datetime.utcnow().isoformat()
    }

    try:
        # Upload credentials to S3
        s3_upload_json(s3_path, test_credentials)
        results.record_pass(
            "Upload credentials to S3",
            f"Successfully uploaded to {s3_path}"
        )

        # Verify file exists
        if s3_file_exists(s3_path):
            results.record_pass(
                "Verify file exists in S3",
                f"File confirmed at {s3_path}"
            )
        else:
            results.record_fail(
                "Verify file exists in S3",
                f"File not found at {s3_path}"
            )

        # Download and verify content
        downloaded_data = s3_download_json(s3_path)
        if downloaded_data == test_credentials:
            results.record_pass(
                "Verify uploaded data matches",
                "Downloaded data matches original"
            )
        else:
            results.record_fail(
                "Verify uploaded data matches",
                "Downloaded data does not match original"
            )

        # Check if encryption is enabled (requires boto3 client)
        try:
            s3_client = get_s3_client()
            bucket_name, key_path = parse_s3_path(s3_path)
            response = s3_client.head_object(Bucket=bucket_name, Key=key_path)

            if 'ServerSideEncryption' in response:
                encryption = response['ServerSideEncryption']
                results.record_pass(
                    "Verify encryption enabled",
                    f"Encryption: {encryption}"
                )
            else:
                results.record_fail(
                    "Verify encryption enabled",
                    "No ServerSideEncryption header found"
                )
        except Exception as e:
            results.record_fail("Verify encryption enabled", str(e))

        # Cleanup
        s3_delete_file(s3_path)
        results.record_pass("Cleanup test file", f"Deleted {s3_path}")

    except Exception as e:
        results.record_fail("Save credentials to S3", str(e))


def test_s3_load_credentials(results: S3TestResults, test_bucket: str):
    """Test Scenario 2: Test Load Credentials from S3"""
    print("\n" + "="*60)
    print("Test Scenario 2: Load Credentials from S3")
    print("="*60)

    test_email = "test-load@example.com"
    s3_path = f"{test_bucket}{test_email}.json"

    # Create test credential data
    test_credentials = {
        "token": "ya29.a0AfH6SMBloadtest",
        "refresh_token": "1//0gZ1loadrefresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "load-test-client.apps.googleusercontent.com",
        "client_secret": "load-test-secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.readonly"],
        "expiry": datetime.utcnow().isoformat()
    }

    try:
        # Upload test file first
        s3_upload_json(s3_path, test_credentials)

        # Test loading
        loaded_data = s3_download_json(s3_path)

        if loaded_data == test_credentials:
            results.record_pass(
                "Load credentials from S3",
                f"Successfully loaded from {s3_path}"
            )
        else:
            results.record_fail(
                "Load credentials from S3",
                "Loaded data does not match expected"
            )

        # Verify JSON structure
        required_fields = ["token", "refresh_token", "token_uri", "client_id", "scopes"]
        missing_fields = [f for f in required_fields if f not in loaded_data]

        if not missing_fields:
            results.record_pass(
                "Verify JSON structure",
                "All required fields present"
            )
        else:
            results.record_fail(
                "Verify JSON structure",
                f"Missing fields: {missing_fields}"
            )

        # Cleanup
        s3_delete_file(s3_path)

    except Exception as e:
        results.record_fail("Load credentials from S3", str(e))


def test_s3_find_any_credentials(results: S3TestResults, test_bucket: str):
    """Test Scenario 3: Test Find Any Credentials in S3 (single-user mode)"""
    print("\n" + "="*60)
    print("Test Scenario 3: Find Any Credentials in S3")
    print("="*60)

    # Upload multiple test credential files
    test_emails = [
        "user1@example.com",
        "user2@example.com",
        "admin@example.com"
    ]

    try:
        # Upload test files
        for email in test_emails:
            s3_path = f"{test_bucket}{email}.json"
            test_creds = {
                "token": f"token-{email}",
                "refresh_token": f"refresh-{email}",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
            }
            s3_upload_json(s3_path, test_creds)

        # List JSON files
        json_files = s3_list_json_files(test_bucket)

        if len(json_files) >= len(test_emails):
            results.record_pass(
                "List credentials in S3",
                f"Found {len(json_files)} credential file(s)"
            )
        else:
            results.record_fail(
                "List credentials in S3",
                f"Expected at least {len(test_emails)}, found {len(json_files)}"
            )

        # Verify all uploaded files are listed
        for email in test_emails:
            expected_path = f"{test_bucket}{email}.json"
            if any(expected_path in f for f in json_files):
                results.record_pass(
                    f"Find {email}",
                    "File found in listing"
                )
            else:
                results.record_fail(
                    f"Find {email}",
                    "File not found in listing"
                )

        # Cleanup
        for email in test_emails:
            s3_path = f"{test_bucket}{email}.json"
            s3_delete_file(s3_path)

    except Exception as e:
        results.record_fail("Find any credentials in S3", str(e))


def test_s3_error_scenarios(results: S3TestResults):
    """Test error handling scenarios"""
    print("\n" + "="*60)
    print("Additional Tests: Error Scenarios")
    print("="*60)

    # Test: File not found
    try:
        non_existent = "s3://test-bucket/nonexistent.json"
        exists = s3_file_exists(non_existent)
        if not exists:
            results.record_pass(
                "Non-existent file check",
                "Correctly returns False for missing file"
            )
        else:
            results.record_fail(
                "Non-existent file check",
                "Should return False for missing file"
            )
    except Exception as e:
        results.record_fail("Non-existent file check", str(e))

    # Test: Invalid S3 path
    try:
        s3_download_json("/local/path/file.json")
        results.record_fail(
            "Invalid path error handling",
            "Should have raised ValueError"
        )
    except ValueError as e:
        if "Invalid S3 path" in str(e):
            results.record_pass(
                "Invalid path error handling",
                "Correctly raises ValueError"
            )
        else:
            results.record_fail(
                "Invalid path error handling",
                f"Wrong error message: {e}"
            )
    except Exception as e:
        results.record_fail("Invalid path error handling", str(e))


def main():
    """Run all S3 storage tests"""
    print("\n" + "="*70)
    print("GOOGLE WORKSPACE MCP - S3 STORAGE MANUAL TESTS (Task 5.2)")
    print("="*70)
    print(f"Test run started: {datetime.now().isoformat()}")

    results = S3TestResults()

    # Always run path detection tests (no AWS credentials needed)
    test_s3_path_detection(results)
    test_s3_error_scenarios(results)

    # Check if AWS credentials are available
    print("\n" + "="*60)
    print("Checking AWS Credentials")
    print("="*60)

    if not check_aws_credentials():
        print("⚠️  AWS credentials not found")
        print("\nTo test S3 operations, configure AWS credentials using one of:")
        print("1. Environment variables:")
        print("   export AWS_ACCESS_KEY_ID=your-key")
        print("   export AWS_SECRET_ACCESS_KEY=your-secret")
        print("   export AWS_REGION=us-east-1")
        print("\n2. AWS credentials file (~/.aws/credentials)")
        print("\n3. IAM role (when running on EC2/ECS/Lambda)")

        results.record_skip(
            "S3 Save/Load/Find tests",
            "AWS credentials not configured"
        )
    else:
        print("✅ AWS credentials found")

        # Get test bucket from environment
        test_bucket = os.getenv(
            'GOOGLE_MCP_CREDENTIALS_DIR',
            's3://test-workspace-mcp-credentials/'
        )

        if not is_s3_path(test_bucket):
            print(f"⚠️  GOOGLE_MCP_CREDENTIALS_DIR is not an S3 path: {test_bucket}")
            print("Using default: s3://test-workspace-mcp-credentials/")
            test_bucket = 's3://test-workspace-mcp-credentials/'

        # Ensure test bucket ends with /
        if not test_bucket.endswith('/'):
            test_bucket += '/'

        print(f"Test bucket: {test_bucket}")

        # Run S3 operation tests
        try:
            test_s3_save_credentials(results, test_bucket)
            test_s3_load_credentials(results, test_bucket)
            test_s3_find_any_credentials(results, test_bucket)
        except Exception as e:
            print(f"\n❌ Test execution error: {e}")
            import traceback
            traceback.print_exc()

    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    summary = results.summary()
    print(f"Total tests:  {summary['total']}")
    print(f"Passed:       {summary['passed']} ✅")
    print(f"Failed:       {summary['failed']} ❌")
    print(f"Skipped:      {summary['skipped']} ⏭️")
    print(f"Pass rate:    {summary['pass_rate']}")

    # Print details of failures
    if results.failed:
        print("\n" + "="*70)
        print("FAILED TESTS")
        print("="*70)
        for test_name, error in results.failed:
            print(f"\n❌ {test_name}")
            print(f"   {error}")

    # Print details of skipped tests
    if results.skipped:
        print("\n" + "="*70)
        print("SKIPPED TESTS")
        print("="*70)
        for test_name, reason in results.skipped:
            print(f"\n⏭️  {test_name}")
            print(f"   {reason}")

    print("\n" + "="*70)
    print(f"Test run completed: {datetime.now().isoformat()}")
    print("="*70)

    # Return exit code
    return 0 if len(results.failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
