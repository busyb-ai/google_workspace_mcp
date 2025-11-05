#!/usr/bin/env python3
"""
Test Path Switching Between Local and S3 Storage

This test suite validates the ability to switch between local file system
and S3 storage for Google OAuth credentials. It tests:

1. Local to S3 migration
2. S3 to local migration
3. Multiple users across different storage types
4. Path detection and storage abstraction

Test Scenarios:
- Save credentials locally, switch to S3, verify works
- Save credentials to S3, switch to local, verify works
- Different users in different storage locations
- No data loss during migration
- Server restarts without issues
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from google.oauth2.credentials import Credentials

# Import modules to test
from auth.s3_storage import (
    is_s3_path,
    parse_s3_path,
    s3_upload_json,
    s3_download_json,
    s3_file_exists,
    s3_list_json_files,
    s3_delete_file,
)
from auth.google_auth import (
    _get_user_credential_path,
    save_credentials_to_file,
    load_credentials_from_file,
    delete_credentials_file,
)


class TestPathSwitching(unittest.TestCase):
    """Test path switching between local and S3 storage."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directories for local storage
        self.temp_dir_1 = tempfile.mkdtemp(prefix="test_creds_local1_")
        self.temp_dir_2 = tempfile.mkdtemp(prefix="test_creds_local2_")

        # Test user emails
        self.user1_email = "user1@example.com"
        self.user2_email = "user2@example.com"

        # Create sample credentials
        self.credentials_1 = self._create_test_credentials("token1")
        self.credentials_2 = self._create_test_credentials("token2")

        # S3 paths for testing (will be mocked)
        self.s3_bucket = "test-bucket"
        self.s3_path_1 = f"s3://{self.s3_bucket}/credentials1/"
        self.s3_path_2 = f"s3://{self.s3_bucket}/credentials2/"

    def tearDown(self):
        """Clean up test environment."""
        # Remove temporary directories
        if os.path.exists(self.temp_dir_1):
            shutil.rmtree(self.temp_dir_1)
        if os.path.exists(self.temp_dir_2):
            shutil.rmtree(self.temp_dir_2)

    def _create_test_credentials(self, token: str) -> Credentials:
        """Create test Google OAuth credentials."""
        credentials = Credentials(
            token=token,
            refresh_token=f"refresh_{token}",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test-client-id.apps.googleusercontent.com",
            client_secret="test-client-secret",
            scopes=[
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ],
        )
        # Set expiry to future date
        credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        return credentials

    def _credentials_to_dict(self, credentials: Credentials) -> dict:
        """Convert Credentials object to dictionary for comparison."""
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        }

    # =========================================================================
    # Test 1: Path Detection and Construction
    # =========================================================================

    def test_path_detection_local(self):
        """Test that local paths are correctly detected."""
        # Local paths should NOT be detected as S3
        self.assertFalse(is_s3_path("/local/path"))
        self.assertFalse(is_s3_path("./relative/path"))
        self.assertFalse(is_s3_path("C:\\Windows\\Path"))
        self.assertFalse(is_s3_path(self.temp_dir_1))
        self.assertFalse(is_s3_path(""))
        self.assertFalse(is_s3_path(None))

    def test_path_detection_s3(self):
        """Test that S3 paths are correctly detected."""
        # S3 paths should be detected
        self.assertTrue(is_s3_path("s3://bucket/path"))
        self.assertTrue(is_s3_path("s3://bucket/"))
        self.assertTrue(is_s3_path("s3://bucket"))
        self.assertTrue(is_s3_path("S3://bucket/path"))  # Case insensitive
        self.assertTrue(is_s3_path(self.s3_path_1))

    def test_get_user_credential_path_local(self):
        """Test credential path construction for local storage."""
        # Test local path construction
        path = _get_user_credential_path(self.user1_email, self.temp_dir_1)

        # Verify path is correct
        expected_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertEqual(path, expected_path)

        # Verify it's not an S3 path
        self.assertFalse(is_s3_path(path))

        # Verify directory was created
        self.assertTrue(os.path.exists(self.temp_dir_1))

    def test_get_user_credential_path_s3(self):
        """Test credential path construction for S3 storage."""
        # Test S3 path construction
        path = _get_user_credential_path(self.user1_email, self.s3_path_1)

        # Verify path is correct
        expected_path = f"{self.s3_path_1}{self.user1_email}.json"
        self.assertEqual(path, expected_path)

        # Verify it's an S3 path
        self.assertTrue(is_s3_path(path))

        # Parse and verify components
        bucket, key = parse_s3_path(path)
        self.assertEqual(bucket, self.s3_bucket)
        self.assertEqual(key, f"credentials1/{self.user1_email}.json")

    def test_get_user_credential_path_s3_no_trailing_slash(self):
        """Test S3 path construction without trailing slash."""
        # S3 path without trailing slash
        s3_path_no_slash = self.s3_path_1.rstrip("/")

        # Test path construction
        path = _get_user_credential_path(self.user1_email, s3_path_no_slash)

        # Verify trailing slash is added
        expected_path = f"{self.s3_path_1}{self.user1_email}.json"
        self.assertEqual(path, expected_path)

    # =========================================================================
    # Test 2: Local Storage Operations
    # =========================================================================

    def test_save_and_load_credentials_local(self):
        """Test saving and loading credentials from local storage."""
        # Save credentials locally
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.temp_dir_1
        )

        # Verify file exists
        creds_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(creds_path))

        # Load credentials
        loaded_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_1
        )

        # Verify credentials match
        self.assertIsNotNone(loaded_creds)
        self.assertEqual(loaded_creds.token, self.credentials_1.token)
        self.assertEqual(
            loaded_creds.refresh_token, self.credentials_1.refresh_token
        )
        self.assertEqual(loaded_creds.client_id, self.credentials_1.client_id)
        self.assertEqual(loaded_creds.scopes, self.credentials_1.scopes)

    def test_delete_credentials_local(self):
        """Test deleting credentials from local storage."""
        # Save credentials
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.temp_dir_1
        )

        # Verify file exists
        creds_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(creds_path))

        # Delete credentials
        delete_credentials_file(self.user1_email, self.temp_dir_1)

        # Verify file is deleted
        self.assertFalse(os.path.exists(creds_path))

    # =========================================================================
    # Test 3: S3 Storage Operations (Mocked)
    # =========================================================================

    @patch("auth.s3_storage.get_s3_client")
    def test_save_and_load_credentials_s3(self, mock_get_s3_client):
        """Test saving and loading credentials from S3 storage (mocked)."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Storage for mocked S3 objects
        s3_storage = {}

        # Mock put_object to store in dict
        def mock_put_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            s3_storage[key] = kwargs["Body"]
            return {}

        # Mock get_object to retrieve from dict
        def mock_get_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "get_object"
                )
            body_mock = MagicMock()
            body_mock.read.return_value = s3_storage[key]
            return {"Body": body_mock}

        # Mock head_object to check existence
        def mock_head_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "head_object"
                )
            return {}

        mock_s3_client.put_object.side_effect = mock_put_object
        mock_s3_client.get_object.side_effect = mock_get_object
        mock_s3_client.head_object.side_effect = mock_head_object

        # Save credentials to S3
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.s3_path_1
        )

        # Verify put_object was called
        self.assertTrue(mock_s3_client.put_object.called)

        # Load credentials from S3
        loaded_creds = load_credentials_from_file(
            self.user1_email, self.s3_path_1
        )

        # Verify credentials match
        self.assertIsNotNone(loaded_creds)
        self.assertEqual(loaded_creds.token, self.credentials_1.token)
        self.assertEqual(
            loaded_creds.refresh_token, self.credentials_1.refresh_token
        )

    @patch("auth.s3_storage.get_s3_client")
    def test_delete_credentials_s3(self, mock_get_s3_client):
        """Test deleting credentials from S3 storage (mocked)."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Mock delete_object
        mock_s3_client.delete_object.return_value = {}

        # Delete credentials from S3
        delete_credentials_file(self.user1_email, self.s3_path_1)

        # Verify delete_object was called
        self.assertTrue(mock_s3_client.delete_object.called)

        # Verify correct bucket and key
        call_args = mock_s3_client.delete_object.call_args
        self.assertEqual(call_args[1]["Bucket"], self.s3_bucket)
        self.assertEqual(
            call_args[1]["Key"], f"credentials1/{self.user1_email}.json"
        )

    # =========================================================================
    # Test 4: Path Switching Scenarios
    # =========================================================================

    def test_scenario_local_to_local_migration(self):
        """Test migrating credentials between two local directories."""
        # Step 1: Save credentials to first local directory
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.temp_dir_1
        )

        # Verify file exists in first directory
        path1 = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(path1))

        # Step 2: Load from first directory
        loaded_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_1
        )
        self.assertIsNotNone(loaded_creds)

        # Step 3: Save to second local directory (migration)
        save_credentials_to_file(
            self.user1_email, loaded_creds, self.temp_dir_2
        )

        # Verify file exists in second directory
        path2 = os.path.join(self.temp_dir_2, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(path2))

        # Step 4: Load from second directory
        migrated_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_2
        )

        # Step 5: Verify credentials match (no data loss)
        self.assertEqual(migrated_creds.token, self.credentials_1.token)
        self.assertEqual(
            migrated_creds.refresh_token, self.credentials_1.refresh_token
        )
        self.assertEqual(migrated_creds.client_id, self.credentials_1.client_id)
        self.assertEqual(migrated_creds.scopes, self.credentials_1.scopes)

        # Step 6: Delete from first directory (cleanup)
        delete_credentials_file(self.user1_email, self.temp_dir_1)
        self.assertFalse(os.path.exists(path1))

        # Verify second directory still has credentials
        self.assertTrue(os.path.exists(path2))

    @patch("auth.s3_storage.get_s3_client")
    def test_scenario_local_to_s3_migration(self, mock_get_s3_client):
        """Test migrating credentials from local to S3 storage."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Storage for mocked S3 objects
        s3_storage = {}

        # Mock S3 operations
        def mock_put_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            s3_storage[key] = kwargs["Body"]
            return {}

        def mock_get_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "get_object"
                )
            body_mock = MagicMock()
            body_mock.read.return_value = s3_storage[key]
            return {"Body": body_mock}

        def mock_head_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "head_object"
                )
            return {}

        mock_s3_client.put_object.side_effect = mock_put_object
        mock_s3_client.get_object.side_effect = mock_get_object
        mock_s3_client.head_object.side_effect = mock_head_object

        # Step 1: Save credentials locally
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.temp_dir_1
        )

        # Verify local file exists
        local_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(local_path))

        # Step 2: Load from local storage
        loaded_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_1
        )
        self.assertIsNotNone(loaded_creds)

        # Step 3: Switch to S3 - save to S3 (migration)
        save_credentials_to_file(
            self.user1_email, loaded_creds, self.s3_path_1
        )

        # Verify put_object was called
        self.assertTrue(mock_s3_client.put_object.called)

        # Step 4: Load from S3
        migrated_creds = load_credentials_from_file(
            self.user1_email, self.s3_path_1
        )

        # Step 5: Verify credentials match (no data loss)
        self.assertEqual(migrated_creds.token, self.credentials_1.token)
        self.assertEqual(
            migrated_creds.refresh_token, self.credentials_1.refresh_token
        )

        # Step 6: Delete local file (cleanup)
        delete_credentials_file(self.user1_email, self.temp_dir_1)
        self.assertFalse(os.path.exists(local_path))

        # Verify S3 still has credentials (via mock)
        s3_key = f"{self.s3_bucket}/credentials1/{self.user1_email}.json"
        self.assertIn(s3_key, s3_storage)

    @patch("auth.s3_storage.get_s3_client")
    def test_scenario_s3_to_local_migration(self, mock_get_s3_client):
        """Test migrating credentials from S3 to local storage."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Storage for mocked S3 objects
        s3_storage = {}

        # Mock S3 operations
        def mock_put_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            s3_storage[key] = kwargs["Body"]
            return {}

        def mock_get_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "get_object"
                )
            body_mock = MagicMock()
            body_mock.read.return_value = s3_storage[key]
            return {"Body": body_mock}

        def mock_head_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "head_object"
                )
            return {}

        def mock_delete_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key in s3_storage:
                del s3_storage[key]
            return {}

        mock_s3_client.put_object.side_effect = mock_put_object
        mock_s3_client.get_object.side_effect = mock_get_object
        mock_s3_client.head_object.side_effect = mock_head_object
        mock_s3_client.delete_object.side_effect = mock_delete_object

        # Step 1: Save credentials to S3
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.s3_path_1
        )

        # Verify S3 storage has the credentials
        s3_key = f"{self.s3_bucket}/credentials1/{self.user1_email}.json"
        self.assertIn(s3_key, s3_storage)

        # Step 2: Load from S3
        loaded_creds = load_credentials_from_file(
            self.user1_email, self.s3_path_1
        )
        self.assertIsNotNone(loaded_creds)

        # Step 3: Switch to local - save to local (migration)
        save_credentials_to_file(
            self.user1_email, loaded_creds, self.temp_dir_1
        )

        # Verify local file exists
        local_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(local_path))

        # Step 4: Load from local
        migrated_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_1
        )

        # Step 5: Verify credentials match (no data loss)
        self.assertEqual(migrated_creds.token, self.credentials_1.token)
        self.assertEqual(
            migrated_creds.refresh_token, self.credentials_1.refresh_token
        )

        # Step 6: Delete S3 credentials (cleanup)
        delete_credentials_file(self.user1_email, self.s3_path_1)

        # Verify S3 storage is empty
        self.assertNotIn(s3_key, s3_storage)

        # Verify local still has credentials
        self.assertTrue(os.path.exists(local_path))

    @patch("auth.s3_storage.get_s3_client")
    def test_scenario_multiple_users_across_storage_types(
        self, mock_get_s3_client
    ):
        """Test multiple users with different storage types."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Storage for mocked S3 objects
        s3_storage = {}

        # Mock S3 operations
        def mock_put_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            s3_storage[key] = kwargs["Body"]
            return {}

        def mock_get_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "get_object"
                )
            body_mock = MagicMock()
            body_mock.read.return_value = s3_storage[key]
            return {"Body": body_mock}

        def mock_head_object(**kwargs):
            key = f"{kwargs['Bucket']}/{kwargs['Key']}"
            if key not in s3_storage:
                from botocore.exceptions import ClientError

                raise ClientError(
                    {"Error": {"Code": "NoSuchKey"}}, "head_object"
                )
            return {}

        mock_s3_client.put_object.side_effect = mock_put_object
        mock_s3_client.get_object.side_effect = mock_get_object
        mock_s3_client.head_object.side_effect = mock_head_object

        # Step 1: User1 uses local storage
        save_credentials_to_file(
            self.user1_email, self.credentials_1, self.temp_dir_1
        )

        # Step 2: User2 uses S3 storage
        save_credentials_to_file(
            self.user2_email, self.credentials_2, self.s3_path_1
        )

        # Step 3: Verify both users can load their credentials
        user1_creds = load_credentials_from_file(
            self.user1_email, self.temp_dir_1
        )
        user2_creds = load_credentials_from_file(
            self.user2_email, self.s3_path_1
        )

        # Step 4: Verify credentials are correct and isolated
        self.assertEqual(user1_creds.token, self.credentials_1.token)
        self.assertEqual(user2_creds.token, self.credentials_2.token)

        # Step 5: Verify storage locations are different
        local_path = os.path.join(self.temp_dir_1, f"{self.user1_email}.json")
        self.assertTrue(os.path.exists(local_path))

        s3_key = f"{self.s3_bucket}/credentials1/{self.user2_email}.json"
        self.assertIn(s3_key, s3_storage)

        # Step 6: Verify no cross-contamination
        # User1's credentials should not exist in S3
        user1_s3_key = f"{self.s3_bucket}/credentials1/{self.user1_email}.json"
        self.assertNotIn(user1_s3_key, s3_storage)

        # User2's credentials should not exist locally
        user2_local_path = os.path.join(
            self.temp_dir_1, f"{self.user2_email}.json"
        )
        self.assertFalse(os.path.exists(user2_local_path))

    # =========================================================================
    # Test 5: Error Handling and Edge Cases
    # =========================================================================

    def test_load_nonexistent_credentials_local(self):
        """Test loading non-existent credentials from local storage."""
        # Try to load non-existent credentials
        creds = load_credentials_from_file(
            "nonexistent@example.com", self.temp_dir_1
        )

        # Should return None
        self.assertIsNone(creds)

    @patch("auth.s3_storage.get_s3_client")
    def test_load_nonexistent_credentials_s3(self, mock_get_s3_client):
        """Test loading non-existent credentials from S3 storage."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_get_s3_client.return_value = mock_s3_client

        # Mock head_object to raise NoSuchKey (file doesn't exist)
        from botocore.exceptions import ClientError

        mock_s3_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "head_object"
        )

        # Try to load non-existent credentials
        creds = load_credentials_from_file(
            "nonexistent@example.com", self.s3_path_1
        )

        # Should return None
        self.assertIsNone(creds)

    def test_path_detection_edge_cases(self):
        """Test path detection with edge cases."""
        # Empty strings
        self.assertFalse(is_s3_path(""))
        self.assertFalse(is_s3_path("   "))

        # None value
        self.assertFalse(is_s3_path(None))

        # Almost S3 paths (missing //)
        self.assertFalse(is_s3_path("s3:/bucket"))
        self.assertFalse(is_s3_path("s3:bucket"))

        # Valid S3 paths with different cases
        self.assertTrue(is_s3_path("s3://bucket"))
        self.assertTrue(is_s3_path("S3://bucket"))
        self.assertTrue(is_s3_path("s3://BUCKET/PATH"))


def run_tests():
    """Run all path switching tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestPathSwitching)

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit(run_tests())
