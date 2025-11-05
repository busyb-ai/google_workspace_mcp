#!/usr/bin/env python3
"""
Local Storage Regression Test Script

This script tests that local file storage still works correctly after adding S3 support.
It validates the backward compatibility of credential management functions.

Test Scenarios:
1. Save credentials to local storage
2. Load credentials from local storage
3. Find any credentials in local directory (single-user mode simulation)
4. Credential path construction with local paths

Author: Claude Code (Task 5.1)
Date: 2025-01-21
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from google.oauth2.credentials import Credentials
from auth.google_auth import (
    save_credentials_to_file,
    load_credentials_from_file,
    _find_any_credentials,
    _get_user_credential_path,
)


class TestResults:
    """Track test results"""
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0

    def add_test(self, name: str, passed: bool, message: str = ""):
        """Add test result"""
        self.tests.append({
            'name': name,
            'passed': passed,
            'message': message
        })
        if passed:
            self.passed += 1
        else:
            self.failed += 1

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        for test in self.tests:
            status = "✓ PASS" if test['passed'] else "✗ FAIL"
            print(f"{status}: {test['name']}")
            if test['message']:
                print(f"  → {test['message']}")
        print("="*80)
        print(f"Total: {len(self.tests)} tests, {self.passed} passed, {self.failed} failed")
        print("="*80)
        return self.failed == 0


def create_test_credentials(email: str = "test@example.com") -> Credentials:
    """Create test credentials object"""
    expiry = datetime.utcnow() + timedelta(hours=1)

    return Credentials(
        token="test_access_token_12345",
        refresh_token="test_refresh_token_67890",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret="test-client-secret",
        scopes=[
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly"
        ],
        expiry=expiry
    )


def test_save_credentials_locally(results: TestResults, test_dir: str):
    """Test saving credentials to local file"""
    print("\n" + "-"*80)
    print("TEST 1: Save Credentials to Local File")
    print("-"*80)

    email = "user1@example.com"

    try:
        # Create test credentials
        credentials = create_test_credentials(email)

        # Save credentials
        save_credentials_to_file(email, credentials, test_dir)

        # Verify file exists
        expected_path = os.path.join(test_dir, f"{email}.json")
        if not os.path.exists(expected_path):
            results.add_test(
                "Save Credentials Locally - File Creation",
                False,
                f"Credential file not created at {expected_path}"
            )
            return

        # Verify file content
        with open(expected_path, 'r') as f:
            data = json.load(f)

        # Check required fields
        required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret', 'scopes', 'expiry']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            results.add_test(
                "Save Credentials Locally - File Format",
                False,
                f"Missing fields in credential file: {missing_fields}"
            )
            return

        # Verify data values
        if data['token'] != credentials.token:
            results.add_test(
                "Save Credentials Locally - Data Integrity",
                False,
                "Token mismatch in saved credentials"
            )
            return

        print(f"✓ Credential file created: {expected_path}")
        print(f"✓ File format valid with all required fields")
        print(f"✓ Token: {data['token'][:20]}...")
        print(f"✓ Scopes: {len(data['scopes'])} scopes saved")

        results.add_test(
            "Save Credentials Locally",
            True,
            f"Successfully saved credentials to {expected_path}"
        )

    except Exception as e:
        results.add_test(
            "Save Credentials Locally",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")


def test_load_credentials_locally(results: TestResults, test_dir: str):
    """Test loading credentials from local file"""
    print("\n" + "-"*80)
    print("TEST 2: Load Credentials from Local File")
    print("-"*80)

    email = "user2@example.com"

    try:
        # First, save credentials
        original_credentials = create_test_credentials(email)
        save_credentials_to_file(email, original_credentials, test_dir)

        # Now load them back
        loaded_credentials = load_credentials_from_file(email, test_dir)

        if loaded_credentials is None:
            results.add_test(
                "Load Credentials Locally",
                False,
                "load_credentials_from_file returned None"
            )
            return

        # Verify loaded credentials match original
        if loaded_credentials.token != original_credentials.token:
            results.add_test(
                "Load Credentials Locally - Token Match",
                False,
                "Loaded token doesn't match original"
            )
            return

        if loaded_credentials.refresh_token != original_credentials.refresh_token:
            results.add_test(
                "Load Credentials Locally - Refresh Token Match",
                False,
                "Loaded refresh token doesn't match original"
            )
            return

        if loaded_credentials.scopes != original_credentials.scopes:
            results.add_test(
                "Load Credentials Locally - Scopes Match",
                False,
                f"Loaded scopes don't match. Original: {original_credentials.scopes}, Loaded: {loaded_credentials.scopes}"
            )
            return

        print(f"✓ Credentials loaded successfully")
        print(f"✓ Token matches: {loaded_credentials.token[:20]}...")
        print(f"✓ Refresh token matches")
        print(f"✓ Scopes match: {len(loaded_credentials.scopes)} scopes")
        print(f"✓ Client ID: {loaded_credentials.client_id}")

        results.add_test(
            "Load Credentials Locally",
            True,
            "Successfully loaded credentials from local file"
        )

    except Exception as e:
        results.add_test(
            "Load Credentials Locally",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")


def test_find_any_credentials_locally(results: TestResults, test_dir: str):
    """Test finding any credentials in local directory (single-user mode simulation)"""
    print("\n" + "-"*80)
    print("TEST 3: Find Any Credentials in Local Directory (Single-User Mode)")
    print("-"*80)

    try:
        # Save multiple credential files
        emails = ["user3@example.com", "user4@example.com", "admin@example.com"]
        for email in emails:
            credentials = create_test_credentials(email)
            save_credentials_to_file(email, credentials, test_dir)

        print(f"✓ Created {len(emails)} credential files")

        # Now try to find any credentials (single-user mode behavior)
        found_credentials = _find_any_credentials(test_dir)

        if found_credentials is None:
            results.add_test(
                "Find Any Credentials Locally",
                False,
                "_find_any_credentials returned None when credentials exist"
            )
            return

        # Verify it's a valid Credentials object
        if not isinstance(found_credentials, Credentials):
            results.add_test(
                "Find Any Credentials Locally",
                False,
                f"_find_any_credentials returned {type(found_credentials)} instead of Credentials"
            )
            return

        # Verify it has required attributes
        if not found_credentials.token or not found_credentials.refresh_token:
            results.add_test(
                "Find Any Credentials Locally - Credential Validity",
                False,
                "Found credentials missing token or refresh_token"
            )
            return

        print(f"✓ Found credentials in directory")
        print(f"✓ Token: {found_credentials.token[:20]}...")
        print(f"✓ Scopes: {len(found_credentials.scopes)} scopes")

        results.add_test(
            "Find Any Credentials Locally",
            True,
            f"Successfully found credentials in {test_dir}"
        )

    except Exception as e:
        results.add_test(
            "Find Any Credentials Locally",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")


def test_credential_path_construction(results: TestResults, test_dir: str):
    """Test credential path construction with local paths"""
    print("\n" + "-"*80)
    print("TEST 4: Credential Path Construction")
    print("-"*80)

    try:
        # Test various path formats
        test_cases = [
            ("user@example.com", test_dir),
            ("admin@company.com", test_dir),
            ("test.user@gmail.com", test_dir),
        ]

        all_passed = True
        for email, base_dir in test_cases:
            path = _get_user_credential_path(email, base_dir)

            # Verify path format
            expected_path = os.path.join(base_dir, f"{email}.json")
            if path != expected_path:
                print(f"✗ Path mismatch for {email}")
                print(f"  Expected: {expected_path}")
                print(f"  Got: {path}")
                all_passed = False
                continue

            # Verify directory exists (should be created by function)
            if not os.path.exists(base_dir):
                print(f"✗ Directory not created: {base_dir}")
                all_passed = False
                continue

            print(f"✓ Path construction correct for {email}: {path}")

        if all_passed:
            results.add_test(
                "Credential Path Construction",
                True,
                "All path construction tests passed"
            )
        else:
            results.add_test(
                "Credential Path Construction",
                False,
                "Some path construction tests failed"
            )

    except Exception as e:
        results.add_test(
            "Credential Path Construction",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")


def test_load_nonexistent_file(results: TestResults, test_dir: str):
    """Test loading credentials from non-existent file (should return None gracefully)"""
    print("\n" + "-"*80)
    print("TEST 5: Load Non-Existent Credentials (Error Handling)")
    print("-"*80)

    try:
        # Try to load credentials that don't exist
        credentials = load_credentials_from_file("nonexistent@example.com", test_dir)

        if credentials is not None:
            results.add_test(
                "Load Non-Existent Credentials",
                False,
                "Expected None for non-existent credentials, got Credentials object"
            )
            return

        print(f"✓ Correctly returned None for non-existent credentials")

        results.add_test(
            "Load Non-Existent Credentials",
            True,
            "Gracefully handled non-existent credential file"
        )

    except Exception as e:
        results.add_test(
            "Load Non-Existent Credentials",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")


def test_empty_directory(results: TestResults):
    """Test finding credentials in empty directory (should return None gracefully)"""
    print("\n" + "-"*80)
    print("TEST 6: Find Credentials in Empty Directory (Error Handling)")
    print("-"*80)

    # Create temporary empty directory
    empty_dir = tempfile.mkdtemp(prefix="empty_test_")

    try:
        # Try to find credentials in empty directory
        credentials = _find_any_credentials(empty_dir)

        if credentials is not None:
            results.add_test(
                "Find Credentials in Empty Directory",
                False,
                "Expected None for empty directory, got Credentials object"
            )
            shutil.rmtree(empty_dir)
            return

        print(f"✓ Correctly returned None for empty directory")

        results.add_test(
            "Find Credentials in Empty Directory",
            True,
            "Gracefully handled empty credential directory"
        )

    except Exception as e:
        results.add_test(
            "Find Credentials in Empty Directory",
            False,
            f"Exception: {str(e)}"
        )
        print(f"✗ Error: {e}")

    finally:
        # Clean up
        shutil.rmtree(empty_dir)


def main():
    """Main test runner"""
    print("="*80)
    print("LOCAL STORAGE REGRESSION TEST")
    print("Task 5.1: Manual Test - Local Storage Regression")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project: Google Workspace MCP - S3 Storage Feature")
    print("="*80)

    # Create test results tracker
    results = TestResults()

    # Create temporary test directory
    test_dir = tempfile.mkdtemp(prefix="test_credentials_")
    print(f"\nTest directory: {test_dir}")

    try:
        # Run all tests
        test_save_credentials_locally(results, test_dir)
        test_load_credentials_locally(results, test_dir)
        test_find_any_credentials_locally(results, test_dir)
        test_credential_path_construction(results, test_dir)
        test_load_nonexistent_file(results, test_dir)
        test_empty_directory(results)

        # Print summary
        all_passed = results.print_summary()

        # Return exit code
        return 0 if all_passed else 1

    finally:
        # Clean up test directory
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
            print(f"\nCleaned up test directory: {test_dir}")


if __name__ == "__main__":
    sys.exit(main())
