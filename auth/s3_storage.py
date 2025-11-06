"""
S3 Storage Abstraction for Google OAuth Credentials

This module provides a storage abstraction layer for Google OAuth credentials,
supporting AWS S3 as an alternative to local file system storage. This enables
centralized credential management across multiple server instances.

Key Features:
- Automatic detection of S3 vs local paths (s3:// prefix)
- S3 path parsing and validation
- JSON credential upload/download with encryption
- File existence checks and directory listing
- Cached S3 client for performance

Storage Options:
- Local: .credentials/{email}.json (default)
- S3: s3://bucket-name/path/{email}.json

AWS Credentials:
The S3 client uses the standard AWS credential chain:
1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
2. AWS credentials file (~/.aws/credentials)
3. IAM role (for EC2/ECS/Lambda)

Security:
- Server-side encryption (SSE-S3) enabled by default
- Private bucket access recommended
- IAM-based access control

Usage Example:
    # Save credentials to S3
    if is_s3_path(creds_path):
        s3_upload_json(creds_path, credentials_dict)

    # Load credentials from S3
    if is_s3_path(creds_path):
        credentials_dict = s3_download_json(creds_path)

    # List credential files
    json_files = s3_list_json_files("s3://bucket/credentials/")
"""

import boto3
import json
import logging
import os
import re
from typing import Optional, Dict, List, Tuple
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
)

# Module-level logger
logger = logging.getLogger(__name__)

# Module-level cache for S3 client (avoid recreating on every operation)
_s3_client = None


def is_s3_path(path: str) -> bool:
    """
    Check if a path is an S3 path.

    Determines whether a given path string represents an S3 location by checking
    if it starts with the 's3://' prefix (case-insensitive). This function handles
    edge cases like None values, empty strings, and whitespace gracefully.

    Args:
        path: Path string to check. Can be a local file path or S3 URI.

    Returns:
        True if path starts with 's3://' (case-insensitive), False otherwise.
        Returns False for None, empty strings, or whitespace-only strings.

    Examples:
        >>> is_s3_path("s3://my-bucket/path/to/file.json")
        True
        >>> is_s3_path("S3://my-bucket/credentials/")
        True
        >>> is_s3_path("/local/path/to/file.json")
        False
        >>> is_s3_path("./relative/path")
        False
        >>> is_s3_path(None)
        False
        >>> is_s3_path("")
        False
        >>> is_s3_path("   ")
        False
    """
    # Handle None input
    if path is None:
        return False

    # Handle empty or whitespace-only strings
    if not path or not path.strip():
        return False

    # Check if path starts with s3:// (case-insensitive)
    return path.strip().lower().startswith("s3://")


def parse_s3_path(s3_path: str) -> Tuple[str, str]:
    """
    Parse S3 path into bucket and key components.

    Extracts the bucket name and object key from an S3 URI. The function validates
    that the input is a valid S3 path, normalizes multiple consecutive slashes to
    single slashes, and handles edge cases like paths without keys or trailing slashes.

    Args:
        s3_path: S3 path in format s3://bucket-name/path/to/key

    Returns:
        Tuple of (bucket_name, key_path) where:
        - bucket_name: The S3 bucket name (string)
        - key_path: The object key path (string, may be empty if no key specified)

    Raises:
        ValueError: If path is not a valid S3 path (doesn't start with s3://)

    Examples:
        >>> parse_s3_path("s3://my-bucket/credentials/user.json")
        ("my-bucket", "credentials/user.json")

        >>> parse_s3_path("s3://my-bucket/path/to/folder/")
        ("my-bucket", "path/to/folder/")

        >>> parse_s3_path("s3://my-bucket/")
        ("my-bucket", "")

        >>> parse_s3_path("s3://my-bucket")
        ("my-bucket", "")

        >>> parse_s3_path("s3://my-bucket//multiple///slashes//file.json")
        ("my-bucket", "multiple/slashes/file.json")

        >>> parse_s3_path("/local/path/to/file")
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: '/local/path/to/file'. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key

        >>> parse_s3_path("")
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: ''. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key
    """
    # Validate that this is an S3 path
    if not is_s3_path(s3_path):
        raise ValueError(
            f"Invalid S3 path: '{s3_path}'. Path must start with 's3://'. "
            f"Use format: s3://bucket-name/path/to/key"
        )

    # Remove the s3:// prefix (case-insensitive)
    # Strip whitespace first, then remove prefix
    path = s3_path.strip()
    # Find the position after 's3://' (case-insensitive)
    prefix_len = len("s3://")
    remaining_path = path[prefix_len:]

    # Split into bucket and key
    # The bucket is everything before the first slash
    # The key is everything after the first slash
    parts = remaining_path.split("/", 1)

    bucket_name = parts[0]

    # Handle case where there's no key (just bucket or bucket with trailing slash)
    if len(parts) == 1:
        key_path = ""
    else:
        key_path = parts[1]

        # Normalize multiple consecutive slashes to single slashes
        # This handles cases like s3://bucket//path///to////file.json
        key_path = re.sub(r'/+', '/', key_path)

        # Remove leading slash if present (from normalization)
        key_path = key_path.lstrip('/')

    return (bucket_name, key_path)


def get_s3_client():
    """
    Get or create cached boto3 S3 client.

    This function provides a cached S3 client to avoid the overhead of creating
    new clients for every operation. The client is initialized once and reused
    for all subsequent calls. The function uses the standard AWS credential chain
    for authentication, making it flexible for different deployment scenarios.

    AWS Credential Chain (in order of precedence):
    1. Environment variables:
       - AWS_ACCESS_KEY_ID
       - AWS_SECRET_ACCESS_KEY
       - AWS_SESSION_TOKEN (optional, for temporary credentials)
    2. AWS credentials file:
       - ~/.aws/credentials (default profile or AWS_PROFILE env var)
    3. IAM role:
       - EC2 instance metadata service
       - ECS task role
       - Lambda execution role

    The AWS region is read from the AWS_REGION environment variable, with a
    default of 'us-east-1' if not specified. The client is configured with
    appropriate timeout settings for production use.

    Returns:
        boto3.client: Configured S3 client instance, cached for reuse

    Raises:
        NoCredentialsError: If AWS credentials are not found in any of the
            standard locations. Error message includes instructions for
            setting up credentials.
        PartialCredentialsError: If AWS credentials are incomplete (e.g.,
            access key ID present but secret access key missing). Error
            message includes instructions for fixing credentials.

    Examples:
        >>> # Using environment variables
        >>> os.environ['AWS_ACCESS_KEY_ID'] = 'your-key-id'
        >>> os.environ['AWS_SECRET_ACCESS_KEY'] = 'your-secret-key'
        >>> os.environ['AWS_REGION'] = 'us-west-2'
        >>> client = get_s3_client()
        >>> client.list_buckets()

        >>> # Using IAM role (no credentials needed)
        >>> # When running on EC2/ECS/Lambda with proper IAM role
        >>> client = get_s3_client()
        >>> client.list_buckets()

        >>> # Using AWS credentials file
        >>> # With credentials in ~/.aws/credentials
        >>> client = get_s3_client()
        >>> client.list_buckets()

    Notes:
        - The client is cached at module level (_s3_client) for performance
        - First call initializes the client, subsequent calls return cached instance
        - Client configuration includes connect_timeout=5s and read_timeout=60s
        - Logs client initialization at INFO level with region information
    """
    global _s3_client

    # Return cached client if available
    if _s3_client is not None:
        return _s3_client

    # Get AWS region from environment, default to us-east-1
    aws_region = os.getenv('AWS_REGION', 'us-east-1')

    try:
        # Create boto3 S3 client with standard credential chain
        # boto3 automatically uses the credential chain:
        # 1. Environment variables
        # 2. AWS credentials file (~/.aws/credentials)
        # 3. IAM role (EC2/ECS/Lambda)
        _s3_client = boto3.client(
            's3',
            region_name=aws_region,
            # Configure timeouts for production use
            config=boto3.session.Config(
                connect_timeout=5,  # Connection timeout in seconds
                read_timeout=60,    # Read timeout in seconds
                retries={
                    'max_attempts': 3,  # Retry failed requests up to 3 times
                    'mode': 'standard'  # Use standard retry mode
                }
            )
        )

        logger.info(
            f"Initialized S3 client for region '{aws_region}' using AWS credential chain"
        )

        return _s3_client

    except NoCredentialsError as e:
        error_msg = (
            "AWS credentials not found. Please configure credentials using one of these methods:\n"
            "1. Environment variables: Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY\n"
            "2. AWS credentials file: Configure ~/.aws/credentials\n"
            "3. IAM role: Ensure EC2/ECS/Lambda instance has proper IAM role attached\n"
            f"Error details: {str(e)}"
        )
        logger.error(error_msg)
        raise NoCredentialsError(error_msg)

    except PartialCredentialsError as e:
        error_msg = (
            "Incomplete AWS credentials found. Both AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY must be set.\n"
            "Please verify your AWS credential configuration:\n"
            "1. Check environment variables: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY\n"
            "2. Check AWS credentials file: ~/.aws/credentials\n"
            f"Error details: {str(e)}"
        )
        logger.error(error_msg)
        raise PartialCredentialsError(error_msg)

    except Exception as e:
        error_msg = f"Unexpected error initializing S3 client: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def s3_file_exists(s3_path: str) -> bool:
    """
    Check if a file exists in S3.

    This function uses the efficient head_object() operation to check file existence
    without downloading the entire file content. It's optimized for performance and
    handles various S3 error scenarios gracefully.

    The function distinguishes between files that don't exist (returns False) and
    actual errors like missing buckets or permission issues (raises exceptions with
    clear messages).

    Args:
        s3_path: S3 path in format s3://bucket-name/path/to/key

    Returns:
        True if file exists in S3, False if file doesn't exist (404/NoSuchKey).

    Raises:
        ValueError: If s3_path is not a valid S3 path (doesn't start with s3://)
        ClientError: If the S3 bucket doesn't exist (NoSuchBucket) or if access
            is denied (AccessDenied). The error message provides actionable
            guidance for resolving the issue.

    Examples:
        >>> # Check if credential file exists
        >>> s3_file_exists("s3://my-bucket/credentials/user@example.com.json")
        True

        >>> # Check non-existent file (returns False, doesn't raise)
        >>> s3_file_exists("s3://my-bucket/credentials/nonexistent.json")
        False

        >>> # Missing bucket raises clear error
        >>> s3_file_exists("s3://nonexistent-bucket/file.json")
        Traceback (most recent call last):
            ...
        ClientError: S3 bucket 'nonexistent-bucket' does not exist. Please verify the bucket name and region, or create the bucket using: aws s3 mb s3://nonexistent-bucket

        >>> # Access denied raises clear error
        >>> s3_file_exists("s3://private-bucket/restricted/file.json")
        Traceback (most recent call last):
            ...
        ClientError: Access denied to S3 bucket 'private-bucket' or key 'restricted/file.json'. Please check your IAM permissions and ensure you have s3:GetObject permission.

    Notes:
        - Uses head_object() instead of get_object() for better performance
        - Logs all existence checks at DEBUG level
        - NoSuchKey (404) is treated as False, not an error
        - NoSuchBucket and AccessDenied raise exceptions with helpful messages
    """
    # Parse S3 path (this also validates it's a valid S3 path)
    bucket_name, key_path = parse_s3_path(s3_path)

    # Log the check at DEBUG level
    logger.debug(f"Checking if file exists in S3: {s3_path}")

    # Get S3 client
    s3_client = get_s3_client()

    try:
        # Use head_object() to check existence without downloading content
        # This is more efficient than get_object()
        s3_client.head_object(Bucket=bucket_name, Key=key_path)

        # If head_object() succeeds, file exists
        logger.debug(f"File exists in S3: {s3_path}")
        return True

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == '404' or error_code == 'NoSuchKey':
            # File doesn't exist - this is expected, return False
            logger.debug(f"File does not exist in S3: {s3_path}")
            return False

        elif error_code == 'NoSuchBucket':
            # Bucket doesn't exist - this is an error, raise with clear message
            error_msg = (
                f"S3 bucket '{bucket_name}' does not exist. "
                f"Please verify the bucket name and region, or create the bucket using: "
                f"aws s3 mb s3://{bucket_name}"
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'NoSuchBucket',
                        'Message': error_msg
                    }
                },
                'head_object'
            )

        elif error_code == '403' or error_code == 'AccessDenied':
            # Access denied - this is an error, raise with clear message
            error_msg = (
                f"Access denied to S3 bucket '{bucket_name}' or key '{key_path}'. "
                f"Please check your IAM permissions and ensure you have s3:GetObject permission."
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': error_msg
                    }
                },
                'head_object'
            )

        else:
            # Other ClientError - log and re-raise
            error_msg = f"Error checking file existence in S3 {s3_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    except Exception as e:
        # Unexpected error - log and raise
        error_msg = f"Unexpected error checking file existence in S3 {s3_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def s3_upload_json(s3_path: str, data: dict) -> None:
    """
    Upload JSON data to S3 with encryption.

    This function serializes a Python dictionary to JSON and uploads it to S3 with
    server-side encryption enabled. The uploaded file is configured with appropriate
    content type metadata and AES256 encryption (SSE-S3) for security.

    The function handles various error scenarios with clear, actionable error messages
    to help users troubleshoot issues with AWS credentials, bucket configuration, and
    permissions.

    Args:
        s3_path: S3 path in format s3://bucket-name/path/to/key.json
        data: Dictionary to serialize and upload as JSON. Must be JSON-serializable.

    Raises:
        ValueError: If s3_path is not a valid S3 path (doesn't start with s3://)
            or if data cannot be serialized to JSON (e.g., contains non-serializable
            objects like datetime without custom encoder).
        ClientError: If the S3 bucket doesn't exist (NoSuchBucket) or if access
            is denied (AccessDenied). Error messages provide specific guidance for
            resolving the issue, including IAM policy suggestions and bucket creation
            commands.
        Exception: For network connectivity issues or other unexpected errors.
            These are logged with full traceback for debugging.

    Examples:
        >>> # Upload credential data to S3
        >>> credentials = {
        ...     "token": "ya29.a0AfH6SMB...",
        ...     "refresh_token": "1//0gZ1...",
        ...     "client_id": "your-client-id.apps.googleusercontent.com",
        ...     "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
        ... }
        >>> s3_upload_json("s3://my-bucket/credentials/user@example.com.json", credentials)
        # Logs: "Uploaded JSON to S3: s3://my-bucket/credentials/user@example.com.json"

        >>> # Upload configuration data
        >>> config = {"setting1": "value1", "setting2": 42}
        >>> s3_upload_json("s3://my-bucket/config/app-config.json", config)

        >>> # Error: Invalid S3 path
        >>> s3_upload_json("/local/path/file.json", {"key": "value"})
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: '/local/path/file.json'. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key

        >>> # Error: Non-serializable data
        >>> import datetime
        >>> s3_upload_json("s3://my-bucket/data.json", {"date": datetime.now()})
        Traceback (most recent call last):
            ...
        ValueError: Failed to serialize data to JSON for upload to s3://my-bucket/data.json. Ensure all data is JSON-serializable. Error: Object of type datetime is not JSON serializable

        >>> # Error: Bucket doesn't exist
        >>> s3_upload_json("s3://nonexistent-bucket/file.json", {"key": "value"})
        Traceback (most recent call last):
            ...
        ClientError: S3 bucket 'nonexistent-bucket' does not exist. Please create the bucket first using: aws s3 mb s3://nonexistent-bucket --region us-east-1

        >>> # Error: Insufficient permissions
        >>> s3_upload_json("s3://restricted-bucket/file.json", {"key": "value"})
        Traceback (most recent call last):
            ...
        ClientError: Access denied to S3 bucket 'restricted-bucket'. Please check your IAM permissions. Required permissions: s3:PutObject. Example IAM policy: {"Effect": "Allow", "Action": ["s3:PutObject"], "Resource": "arn:aws:s3:::restricted-bucket/*"}

    Notes:
        - Uploaded files have Content-Type: application/json
        - Server-side encryption (SSE-S3) with AES256 is enabled by default
        - Successful uploads are logged at INFO level with the S3 path
        - Failed uploads are logged at ERROR level with detailed error information
        - The function performs a complete overwrite of existing files with the same path
        - JSON serialization uses default encoding (no custom encoder)
    """
    # Parse S3 path (this also validates it's a valid S3 path)
    bucket_name, key_path = parse_s3_path(s3_path)

    # Serialize data to JSON string
    try:
        json_string = json.dumps(data, indent=2)
    except (TypeError, ValueError) as e:
        error_msg = (
            f"Failed to serialize data to JSON for upload to {s3_path}. "
            f"Ensure all data is JSON-serializable. Error: {str(e)}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Get S3 client
    s3_client = get_s3_client()

    try:
        # Upload to S3 with encryption and proper content type
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key_path,
            Body=json_string.encode('utf-8'),
            ContentType='application/json',
            ServerSideEncryption='AES256'  # Enable SSE-S3 encryption
        )

        # Log successful upload
        logger.info(f"Uploaded JSON to S3: {s3_path}")

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'NoSuchBucket':
            # Bucket doesn't exist - provide bucket creation guidance
            aws_region = os.getenv('AWS_REGION', 'us-east-1')
            error_msg = (
                f"S3 bucket '{bucket_name}' does not exist. "
                f"Please create the bucket first using: "
                f"aws s3 mb s3://{bucket_name} --region {aws_region}"
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'NoSuchBucket',
                        'Message': error_msg
                    }
                },
                'put_object'
            )

        elif error_code == '403' or error_code == 'AccessDenied':
            # Access denied - provide IAM policy guidance
            error_msg = (
                f"Access denied to S3 bucket '{bucket_name}'. "
                f"Please check your IAM permissions. Required permissions: s3:PutObject. "
                f"Example IAM policy: "
                f'{{"Effect": "Allow", "Action": ["s3:PutObject"], "Resource": "arn:aws:s3:::{bucket_name}/*"}}'
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': error_msg
                    }
                },
                'put_object'
            )

        else:
            # Other ClientError - log and re-raise
            error_msg = f"Error uploading JSON to S3 {s3_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    except Exception as e:
        # Unexpected error (e.g., network issues) - log and raise
        error_msg = f"Unexpected error uploading JSON to S3 {s3_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def s3_download_json(s3_path: str) -> dict:
    """
    Download and parse JSON data from S3.

    This function downloads a JSON file from S3 and parses it into a Python dictionary.
    It handles various error scenarios gracefully, including missing files, missing buckets,
    permission issues, and corrupted JSON data.

    The function uses get_object() to download the file content, decodes it as UTF-8,
    and parses it as JSON. All operations are logged at DEBUG level for troubleshooting.

    Args:
        s3_path: S3 path in format s3://bucket-name/path/to/key.json

    Returns:
        Parsed JSON data as dictionary. The structure depends on the JSON file content.

    Raises:
        ValueError: If s3_path is not a valid S3 path (doesn't start with s3://),
            if the file doesn't exist (NoSuchKey), or if the JSON cannot be parsed
            (corrupt or invalid JSON). Error messages provide specific guidance for
            resolving the issue.
        ClientError: If the S3 bucket doesn't exist (NoSuchBucket) or if access
            is denied (AccessDenied). Error messages include specific IAM permission
            requirements and troubleshooting steps.
        Exception: For network connectivity issues or other unexpected errors.
            These are logged with full traceback for debugging.

    Examples:
        >>> # Download credential data from S3
        >>> credentials = s3_download_json("s3://my-bucket/credentials/user@example.com.json")
        >>> print(credentials)
        {
            "token": "ya29.a0AfH6SMB...",
            "refresh_token": "1//0gZ1...",
            "client_id": "your-client-id.apps.googleusercontent.com",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
        }

        >>> # Download configuration data
        >>> config = s3_download_json("s3://my-bucket/config/app-config.json")
        >>> print(config["setting1"])
        value1

        >>> # Error: Invalid S3 path
        >>> s3_download_json("/local/path/file.json")
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: '/local/path/file.json'. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key

        >>> # Error: File doesn't exist
        >>> s3_download_json("s3://my-bucket/credentials/nonexistent.json")
        Traceback (most recent call last):
            ...
        ValueError: File not found in S3: s3://my-bucket/credentials/nonexistent.json. Please verify the file path and ensure the file exists in the bucket.

        >>> # Error: Bucket doesn't exist
        >>> s3_download_json("s3://nonexistent-bucket/file.json")
        Traceback (most recent call last):
            ...
        ClientError: S3 bucket 'nonexistent-bucket' does not exist. Please verify the bucket name and region.

        >>> # Error: Corrupted JSON file
        >>> # (assuming 'corrupted.json' contains invalid JSON like "invalid json{")
        >>> s3_download_json("s3://my-bucket/corrupted.json")
        Traceback (most recent call last):
            ...
        ValueError: Failed to parse JSON from S3 file s3://my-bucket/corrupted.json. The file may be corrupted or contain invalid JSON. Error: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)

        >>> # Error: Insufficient permissions
        >>> s3_download_json("s3://restricted-bucket/private/file.json")
        Traceback (most recent call last):
            ...
        ClientError: Access denied to S3 bucket 'restricted-bucket' or key 'private/file.json'. Please check your IAM permissions. Required permissions: s3:GetObject. Example IAM policy: {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::restricted-bucket/*"}

    Notes:
        - Downloads are logged at DEBUG level with the S3 path
        - The function assumes the file contains valid UTF-8 encoded JSON
        - File content is fully downloaded into memory before parsing
        - NoSuchKey errors are converted to ValueError (file not found)
        - All other errors are logged with detailed context for debugging
    """
    # Parse S3 path (this also validates it's a valid S3 path)
    bucket_name, key_path = parse_s3_path(s3_path)

    # Log the download at DEBUG level
    logger.debug(f"Downloading JSON from S3: {s3_path}")

    # Get S3 client
    s3_client = get_s3_client()

    try:
        # Download file from S3
        response = s3_client.get_object(Bucket=bucket_name, Key=key_path)

        # Read response body and decode as UTF-8
        json_content = response['Body'].read().decode('utf-8')

        # Parse JSON string to dictionary
        try:
            data = json.loads(json_content)
            logger.debug(f"Successfully downloaded and parsed JSON from S3: {s3_path}")
            return data
        except json.JSONDecodeError as e:
            # JSON parsing failed - corrupted or invalid JSON
            error_msg = (
                f"Failed to parse JSON from S3 file {s3_path}. "
                f"The file may be corrupted or contain invalid JSON. "
                f"Error: {str(e)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == '404' or error_code == 'NoSuchKey':
            # File doesn't exist - raise ValueError with clear message
            error_msg = (
                f"File not found in S3: {s3_path}. "
                f"Please verify the file path and ensure the file exists in the bucket."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        elif error_code == 'NoSuchBucket':
            # Bucket doesn't exist - raise with bucket verification message
            error_msg = (
                f"S3 bucket '{bucket_name}' does not exist. "
                f"Please verify the bucket name and region."
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'NoSuchBucket',
                        'Message': error_msg
                    }
                },
                'get_object'
            )

        elif error_code == '403' or error_code == 'AccessDenied':
            # Access denied - raise with permissions message
            error_msg = (
                f"Access denied to S3 bucket '{bucket_name}' or key '{key_path}'. "
                f"Please check your IAM permissions. Required permissions: s3:GetObject. "
                f"Example IAM policy: "
                f'{{"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::{bucket_name}/*"}}'
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': error_msg
                    }
                },
                'get_object'
            )

        else:
            # Other ClientError - log and re-raise
            error_msg = f"Error downloading JSON from S3 {s3_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    except Exception as e:
        # Unexpected error - log with traceback and raise
        error_msg = f"Unexpected error downloading JSON from S3 {s3_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def s3_list_json_files(s3_dir: str) -> List[str]:
    """
    List all JSON files in an S3 directory (prefix).

    This function lists all objects in an S3 bucket with a given prefix and filters
    the results to include only files with a .json extension. It handles pagination
    automatically to ensure all results are returned, even for directories with
    thousands of files.

    The function returns full S3 paths (s3://bucket/key) for each JSON file found,
    making it easy to pass these paths directly to other S3 functions like
    s3_download_json() or s3_file_exists().

    Args:
        s3_dir: S3 directory path in format s3://bucket-name/path/to/dir/
                The trailing slash is optional but recommended for clarity.

    Returns:
        List of full S3 paths to JSON files (e.g., ["s3://bucket/file1.json", ...]).
        Returns empty list if the directory is empty, doesn't exist, or contains
        no JSON files. The list is not sorted by default.

    Raises:
        ValueError: If s3_dir is not a valid S3 path (doesn't start with s3://)
        ClientError: If the S3 bucket doesn't exist (NoSuchBucket) or if access
            is denied (AccessDenied). Error messages provide specific guidance for
            resolving the issue, including required IAM permissions.

    Examples:
        >>> # List credential files in S3
        >>> files = s3_list_json_files("s3://my-bucket/credentials/")
        >>> print(files)
        ["s3://my-bucket/credentials/user1@gmail.com.json",
         "s3://my-bucket/credentials/user2@gmail.com.json",
         "s3://my-bucket/credentials/admin@example.com.json"]

        >>> # List files with nested prefix
        >>> files = s3_list_json_files("s3://my-bucket/app/configs/")
        >>> print(files)
        ["s3://my-bucket/app/configs/dev.json",
         "s3://my-bucket/app/configs/prod.json"]

        >>> # Empty directory returns empty list
        >>> files = s3_list_json_files("s3://my-bucket/empty-dir/")
        >>> print(files)
        []

        >>> # Directory with no JSON files returns empty list
        >>> # (e.g., contains only .txt or .csv files)
        >>> files = s3_list_json_files("s3://my-bucket/non-json-dir/")
        >>> print(files)
        []

        >>> # Works with or without trailing slash
        >>> files1 = s3_list_json_files("s3://my-bucket/credentials/")
        >>> files2 = s3_list_json_files("s3://my-bucket/credentials")
        >>> files1 == files2
        True

        >>> # Error: Invalid S3 path
        >>> s3_list_json_files("/local/path/")
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: '/local/path/'. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key

        >>> # Error: Bucket doesn't exist
        >>> s3_list_json_files("s3://nonexistent-bucket/dir/")
        Traceback (most recent call last):
            ...
        ClientError: S3 bucket 'nonexistent-bucket' does not exist. Please verify the bucket name and region.

        >>> # Error: Insufficient permissions
        >>> s3_list_json_files("s3://restricted-bucket/private/")
        Traceback (most recent call last):
            ...
        ClientError: Access denied to S3 bucket 'restricted-bucket'. Please check your IAM permissions. Required permissions: s3:ListBucket. Example IAM policy: {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::restricted-bucket"}

    Notes:
        - Handles pagination automatically using ContinuationToken
        - Filters out non-JSON files (only includes files ending with .json)
        - Returns full S3 paths, not just keys
        - Empty results are not an error (returns empty list)
        - Files are not sorted; order depends on S3's internal organization
        - Subdirectories are traversed (lists all .json files recursively under prefix)
        - Logs the count of JSON files found at INFO level
        - Does not follow S3 "directory" semantics (S3 is a flat namespace)
    """
    # Parse S3 path (this also validates it's a valid S3 path)
    bucket_name, prefix = parse_s3_path(s3_dir)

    # Ensure prefix ends with '/' for proper directory listing
    # (unless it's empty, which means list from bucket root)
    if prefix and not prefix.endswith('/'):
        prefix += '/'

    # Get S3 client
    s3_client = get_s3_client()

    # List to accumulate all JSON file paths
    json_files = []

    # Pagination token for handling large result sets
    continuation_token = None

    try:
        # Loop to handle paginated results
        while True:
            # Build list_objects_v2 parameters
            list_params = {
                'Bucket': bucket_name,
                'Prefix': prefix
            }

            # Add continuation token if this is a paginated request
            if continuation_token:
                list_params['ContinuationToken'] = continuation_token

            # List objects with the given prefix
            response = s3_client.list_objects_v2(**list_params)

            # Check if any objects were returned
            if 'Contents' in response:
                # Filter for JSON files and build full S3 paths
                for obj in response['Contents']:
                    key = obj['Key']
                    # Only include files ending with .json (case-insensitive)
                    if key.lower().endswith('.json'):
                        full_s3_path = f"s3://{bucket_name}/{key}"
                        json_files.append(full_s3_path)

            # Check if there are more results to fetch
            if response.get('IsTruncated', False):
                # Get continuation token for next page
                continuation_token = response.get('NextContinuationToken')
                if not continuation_token:
                    # Safety check: IsTruncated is True but no token
                    # This shouldn't happen, but break to avoid infinite loop
                    logger.warning(
                        f"S3 list response indicated truncated results but no continuation token provided for {s3_dir}"
                    )
                    break
            else:
                # No more results, exit loop
                break

        # Log count of files found
        logger.info(f"Found {len(json_files)} JSON file(s) in S3 directory: {s3_dir}")

        return json_files

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'NoSuchBucket':
            # Bucket doesn't exist - raise with bucket verification message
            error_msg = (
                f"S3 bucket '{bucket_name}' does not exist. "
                f"Please verify the bucket name and region."
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'NoSuchBucket',
                        'Message': error_msg
                    }
                },
                'list_objects_v2'
            )

        elif error_code == '403' or error_code == 'AccessDenied':
            # Access denied - raise with ListBucket permission message
            error_msg = (
                f"Access denied to S3 bucket '{bucket_name}'. "
                f"Please check your IAM permissions. Required permissions: s3:ListBucket. "
                f"Example IAM policy: "
                f'{{"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::{bucket_name}"}}'
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': error_msg
                    }
                },
                'list_objects_v2'
            )

        else:
            # Other ClientError - log and re-raise
            error_msg = f"Error listing JSON files in S3 directory {s3_dir}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    except Exception as e:
        # Unexpected error - log with traceback and raise
        error_msg = f"Unexpected error listing JSON files in S3 directory {s3_dir}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise


def s3_delete_file(s3_path: str) -> None:
    """
    Delete a file from S3.

    This function deletes an object from S3. The operation is idempotent, meaning
    that deleting a non-existent file does not raise an error - S3 will return
    success in both cases. This behavior simplifies cleanup operations where you
    want to ensure a file is deleted regardless of whether it currently exists.

    The function handles various error scenarios with clear, actionable error messages
    to help users troubleshoot issues with bucket configuration and permissions.

    Args:
        s3_path: S3 path in format s3://bucket-name/path/to/key

    Raises:
        ValueError: If s3_path is not a valid S3 path (doesn't start with s3://)
        ClientError: If the S3 bucket doesn't exist (NoSuchBucket) or if access
            is denied (AccessDenied). Error messages provide specific guidance for
            resolving the issue, including required IAM permissions.

    Examples:
        >>> # Delete existing credential file
        >>> s3_delete_file("s3://my-bucket/credentials/user@example.com.json")
        # Logs: "Deleted file from S3: s3://my-bucket/credentials/user@example.com.json"

        >>> # Delete non-existent file (no error - idempotent)
        >>> s3_delete_file("s3://my-bucket/credentials/nonexistent.json")
        # Logs: "Deleted file from S3: s3://my-bucket/credentials/nonexistent.json"
        # No error raised even though file doesn't exist

        >>> # Delete multiple files in cleanup operation
        >>> for email in ["user1@example.com", "user2@example.com"]:
        ...     s3_delete_file(f"s3://my-bucket/credentials/{email}.json")

        >>> # Error: Invalid S3 path
        >>> s3_delete_file("/local/path/file.json")
        Traceback (most recent call last):
            ...
        ValueError: Invalid S3 path: '/local/path/file.json'. Path must start with 's3://'. Use format: s3://bucket-name/path/to/key

        >>> # Error: Bucket doesn't exist
        >>> s3_delete_file("s3://nonexistent-bucket/file.json")
        Traceback (most recent call last):
            ...
        ClientError: S3 bucket 'nonexistent-bucket' does not exist. Please verify the bucket name and region.

        >>> # Error: Insufficient permissions
        >>> s3_delete_file("s3://restricted-bucket/file.json")
        Traceback (most recent call last):
            ...
        ClientError: Access denied to S3 bucket 'restricted-bucket'. Please check your IAM permissions. Required permissions: s3:DeleteObject. Example IAM policy: {"Effect": "Allow", "Action": ["s3:DeleteObject"], "Resource": "arn:aws:s3:::restricted-bucket/*"}

    Notes:
        - This operation is idempotent - deleting a non-existent file does NOT raise an error
        - S3's delete_object() returns success whether the file exists or not
        - Successful deletions are logged at INFO level with the S3 path
        - NoSuchBucket and AccessDenied errors are raised with helpful messages
        - Use this for credential cleanup, temporary file removal, etc.
        - No way to verify if file existed before deletion (S3 limitation)
    """
    # Parse S3 path (this also validates it's a valid S3 path)
    bucket_name, key_path = parse_s3_path(s3_path)

    # Get S3 client
    s3_client = get_s3_client()

    try:
        # Delete object from S3
        # Note: S3 delete_object() is idempotent - it succeeds even if the object doesn't exist
        # This is by design and simplifies cleanup operations
        s3_client.delete_object(Bucket=bucket_name, Key=key_path)

        # Log successful deletion
        logger.info(f"Deleted file from S3: {s3_path}")

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == 'NoSuchBucket':
            # Bucket doesn't exist - raise with bucket verification message
            error_msg = (
                f"S3 bucket '{bucket_name}' does not exist. "
                f"Please verify the bucket name and region."
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'NoSuchBucket',
                        'Message': error_msg
                    }
                },
                'delete_object'
            )

        elif error_code == '403' or error_code == 'AccessDenied':
            # Access denied - raise with DeleteObject permission message
            error_msg = (
                f"Access denied to S3 bucket '{bucket_name}'. "
                f"Please check your IAM permissions. Required permissions: s3:DeleteObject. "
                f"Example IAM policy: "
                f'{{"Effect": "Allow", "Action": ["s3:DeleteObject"], "Resource": "arn:aws:s3:::{bucket_name}/*"}}'
            )
            logger.error(error_msg)
            raise ClientError(
                {
                    'Error': {
                        'Code': 'AccessDenied',
                        'Message': error_msg
                    }
                },
                'delete_object'
            )

        else:
            # Other ClientError - log and re-raise
            error_msg = f"Error deleting file from S3 {s3_path}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise

    except Exception as e:
        # Unexpected error - log with traceback and raise
        error_msg = f"Unexpected error deleting file from S3 {s3_path}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise
