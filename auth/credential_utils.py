"""
Credential storage utilities for Google Workspace MCP.

This module contains shared utility functions for credential file management
that are used by both google_auth.py and oauth21_session_store.py.
It exists as a separate module to avoid circular imports.
"""

import json
import logging
import os
from typing import Optional

from google.oauth2.credentials import Credentials
from datetime import datetime

from auth.s3_storage import is_s3_path, s3_upload_json, s3_file_exists, s3_download_json

logger = logging.getLogger(__name__)


def get_default_credentials_dir() -> str:
    """
    Get the default credentials directory path, preferring user-specific locations.

    Returns:
        Path to credentials directory (local or S3)
    """
    # Check for explicit environment variable override
    if os.getenv("GOOGLE_MCP_CREDENTIALS_DIR"):
        return os.getenv("GOOGLE_MCP_CREDENTIALS_DIR")

    # Use user home directory for credentials storage
    home_dir = os.path.expanduser("~")
    if home_dir and home_dir != "~":  # Valid home directory found
        return os.path.join(home_dir, ".google_workspace_mcp", "credentials")

    # Fallback to current working directory if home directory is not accessible
    return os.path.join(os.getcwd(), ".credentials")


def get_user_credential_path(
    credential_identifier: str, base_dir: Optional[str] = None
) -> str:
    """
    Constructs the path to a user's credential file (local or S3).

    This function supports both local file system paths and S3 paths. It automatically
    detects the storage type based on the path prefix (s3:// for S3, otherwise local).

    Args:
        credential_identifier: User identifier (user_id) used as filename
        base_dir: Base directory path (local path or S3 URI in format s3://bucket/path/)
                 If None, uses get_default_credentials_dir()

    Returns:
        Full path to credential file:
        - For local: /path/to/dir/{user_id}.json
        - For S3: s3://bucket/path/{user_id}.json

    Examples:
        >>> # Local path
        >>> get_user_credential_path("user123", "/credentials")
        '/credentials/user123.json'

        >>> # S3 path
        >>> get_user_credential_path("user123", "s3://my-bucket/credentials")
        's3://my-bucket/credentials/user123.json'

        >>> # S3 path with trailing slash
        >>> get_user_credential_path("user123", "s3://my-bucket/credentials/")
        's3://my-bucket/credentials/user123.json'
    """
    if base_dir is None:
        base_dir = get_default_credentials_dir()

    if is_s3_path(base_dir):
        # S3 path - ensure trailing slash and append filename
        # No directory creation needed for S3 (S3 is a flat namespace)
        if not base_dir.endswith('/'):
            base_dir += '/'
        return f"{base_dir}{credential_identifier}.json"
    else:
        # Local path - create directory if needed
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            logger.info(f"Created credentials directory: {base_dir}")
        return os.path.join(base_dir, f"{credential_identifier}.json")


def load_credentials_from_file(
    credential_identifier: str, base_dir: Optional[str] = None
) -> Optional[Credentials]:
    """
    Loads user credentials from a file or S3.

    Args:
        credential_identifier: User identifier (user_id) for credential file naming
        base_dir: Base directory path (local or S3). If None, uses get_default_credentials_dir()

    Returns:
        Credentials object if found, None otherwise
    """
    if base_dir is None:
        base_dir = get_default_credentials_dir()

    creds_path = get_user_credential_path(credential_identifier, base_dir)

    try:
        if is_s3_path(creds_path):
            # Check if file exists in S3
            if not s3_file_exists(creds_path):
                logger.info(
                    f"No credentials file found for identifier {credential_identifier} in S3: {creds_path}"
                )
                return None

            # Download from S3
            creds_data = s3_download_json(creds_path)
            logger.debug(f"Downloaded credentials from S3 for identifier {credential_identifier}")
        else:
            # Load from local file
            if not os.path.exists(creds_path):
                logger.info(
                    f"No credentials file found for identifier {credential_identifier} at {creds_path}"
                )
                return None

            with open(creds_path, "r") as f:
                creds_data = json.load(f)
            logger.debug(f"Loaded credentials from local file for identifier {credential_identifier}")

        # Parse expiry if present
        expiry = None
        if creds_data.get("expiry"):
            try:
                expiry = datetime.fromisoformat(creds_data["expiry"])
                # Ensure timezone-naive datetime for Google auth library compatibility
                if expiry.tzinfo is not None:
                    expiry = expiry.replace(tzinfo=None)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Could not parse expiry time for identifier {credential_identifier}: {e}"
                )

        # Create Credentials object
        credentials = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=creds_data.get("scopes"),
            expiry=expiry,
        )

        logger.debug(
            f"Credentials loaded for identifier {credential_identifier} from {creds_path}"
        )
        return credentials

    except (IOError, json.JSONDecodeError, KeyError) as e:
        logger.error(
            f"Error loading or parsing credentials for identifier {credential_identifier} from {creds_path}: {e}"
        )
        return None


def save_credentials_to_file(
    credential_identifier: str,
    user_google_email: str,
    credentials: Credentials,
    base_dir: Optional[str] = None,
):
    """
    Saves user credentials to a file or S3.

    Supports both local file storage and AWS S3 storage. Storage location is determined
    by the base_dir path format:
    - Local: /path/to/credentials/
    - S3: s3://bucket-name/path/

    Args:
        credential_identifier: User identifier (user_id) for credential file naming
        user_google_email: User's Google email address (stored in file for reference)
        credentials: Google OAuth credentials object
        base_dir: Base directory path (local or S3). If None, uses get_default_credentials_dir()

    Raises:
        IOError: If local file write fails
        ClientError: If S3 upload fails
        Exception: For other errors during credential save
    """
    if base_dir is None:
        base_dir = get_default_credentials_dir()

    creds_path = get_user_credential_path(credential_identifier, base_dir)
    creds_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
        "user_email": user_google_email,  # Store email in the file for reference
    }

    try:
        if is_s3_path(creds_path):
            # Upload to S3
            s3_upload_json(creds_path, creds_data)
            logger.info(f"Credentials saved for user {user_google_email} to S3: {creds_path}")
        else:
            # Save to local file
            with open(creds_path, "w") as f:
                json.dump(creds_data, f)
            logger.info(f"Credentials saved for user {user_google_email} to {creds_path}")
    except Exception as e:
        logger.error(
            f"Error saving credentials for user {user_google_email} (identifier: {credential_identifier}) to {creds_path}: {e}"
        )
        raise
