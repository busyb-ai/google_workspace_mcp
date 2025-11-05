# Task 2.1: Update `_get_user_credential_path()` for S3 Support - Summary

## Task Overview
Updated the `_get_user_credential_path()` function in `auth/google_auth.py` to support both local file system paths and S3 paths, enabling flexible credential storage options.

## Changes Made

### 1. Import Statement (Line 20)
**Added:**
```python
from auth.s3_storage import is_s3_path
```

**Location:** After `from auth.oauth21_session_store import get_oauth21_session_store` (line 19)

### 2. Function Update (Lines 116-158)

**Original function (lines 115-122):**
```python
def _get_user_credential_path(
    user_google_email: str, base_dir: str = DEFAULT_CREDENTIALS_DIR
) -> str:
    """Constructs the path to a user's credential file."""
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        logger.info(f"Created credentials directory: {base_dir}")
    return os.path.join(base_dir, f"{user_google_email}.json")
```

**Updated function (lines 116-158):**
```python
def _get_user_credential_path(
    user_google_email: str, base_dir: str = DEFAULT_CREDENTIALS_DIR
) -> str:
    """
    Constructs the path to a user's credential file (local or S3).

    This function supports both local file system paths and S3 paths. It automatically
    detects the storage type based on the path prefix (s3:// for S3, otherwise local).

    Args:
        user_google_email: User's Google email address (used as filename)
        base_dir: Base directory path (local path or S3 URI in format s3://bucket/path/)

    Returns:
        Full path to credential file:
        - For local: /path/to/dir/{email}.json
        - For S3: s3://bucket/path/{email}.json

    Examples:
        >>> # Local path
        >>> _get_user_credential_path("user@example.com", "/credentials")
        '/credentials/user@example.com.json'

        >>> # S3 path
        >>> _get_user_credential_path("user@example.com", "s3://my-bucket/credentials")
        's3://my-bucket/credentials/user@example.com.json'

        >>> # S3 path with trailing slash
        >>> _get_user_credential_path("user@example.com", "s3://my-bucket/credentials/")
        's3://my-bucket/credentials/user@example.com.json'
    """
    if is_s3_path(base_dir):
        # S3 path - ensure trailing slash and append filename
        # No directory creation needed for S3 (S3 is a flat namespace)
        if not base_dir.endswith('/'):
            base_dir += '/'
        return f"{base_dir}{user_google_email}.json"
    else:
        # Local path - create directory if needed (existing logic)
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)
            logger.info(f"Created credentials directory: {base_dir}")
        return os.path.join(base_dir, f"{user_google_email}.json")
```

## Key Implementation Details

### S3 Path Handling
- **Detection:** Uses `is_s3_path()` from `auth.s3_storage` to check if `base_dir` starts with `s3://`
- **Path Construction:** Simple string concatenation after ensuring trailing slash
- **No Directory Creation:** S3 is a flat namespace, no need to create directories
- **Trailing Slash Handling:** Automatically adds `/` if missing to ensure proper path joining

### Local Path Handling
- **Preserved Behavior:** Kept all existing logic unchanged
- **Directory Creation:** Still creates local directories if they don't exist
- **Path Construction:** Still uses `os.path.join()` for proper OS-specific path handling

### Docstring Enhancements
- Added comprehensive description explaining S3 support
- Included detailed Args and Returns sections with type information
- Added three usage examples covering local paths, S3 paths, and S3 paths with trailing slashes

## Acceptance Criteria - Status

✅ **Function correctly detects S3 vs local paths** - Uses `is_s3_path()` for detection
✅ **S3 paths return properly formatted S3 URIs** - Returns `s3://bucket/path/email.json`
✅ **S3 paths handle missing trailing slashes** - Adds `/` if not present
✅ **Local paths still create directories as before** - Preserved existing logic in else block
✅ **Docstring updated to mention S3 support** - Comprehensive docstring with examples
✅ **No changes to function signature** - Parameters unchanged: `(user_google_email, base_dir)`
✅ **Backward compatible with existing code** - Local path handling unchanged

## Testing Notes

### Import Test Status
- **Status:** Cannot test imports yet (blocked by missing boto3 dependency)
- **Reason:** `auth.s3_storage` requires `boto3` which is added in Task 3.1
- **Next Step:** Import testing will be possible after completing Task 3.1 and 3.2

### Syntax Verification
- ✅ Code structure is correct
- ✅ Import statement properly placed (line 20)
- ✅ Function logic follows task requirements exactly
- ✅ Docstring formatting is correct

## Example Usage

### Local Storage (Existing Behavior)
```python
path = _get_user_credential_path("user@example.com", "/home/user/.credentials")
# Returns: "/home/user/.credentials/user@example.com.json"
# Side effect: Creates /home/user/.credentials if it doesn't exist
```

### S3 Storage (New Feature)
```python
# Without trailing slash
path = _get_user_credential_path("user@example.com", "s3://my-bucket/credentials")
# Returns: "s3://my-bucket/credentials/user@example.com.json"

# With trailing slash
path = _get_user_credential_path("user@example.com", "s3://my-bucket/credentials/")
# Returns: "s3://my-bucket/credentials/user@example.com.json"
# (Both return the same result)
```

## Files Modified

1. **auth/google_auth.py**
   - Line 20: Added `from auth.s3_storage import is_s3_path`
   - Lines 116-158: Updated `_get_user_credential_path()` function with S3 support and enhanced docstring

## Dependencies

This implementation depends on:
- `auth.s3_storage.is_s3_path` - Function to detect S3 paths (implemented in Phase 1, Task 1.2)
- `boto3` - AWS SDK for Python (to be added in Task 3.1)

## Regression Risk Assessment

**Risk Level: LOW**

- Local path behavior completely unchanged (preserved in else block)
- New S3 logic only executes when `is_s3_path()` returns True
- No modifications to function signature or return type
- Backward compatible with all existing callers

## Next Steps

1. **Task 2.2:** Update `save_credentials_to_file()` to use S3 upload
2. **Task 2.3:** Update `load_credentials_from_file()` to use S3 download
3. **Task 2.4:** Update `_find_any_credentials()` to list S3 files
4. **Task 3.1-3.2:** Add boto3 dependency and sync with uv (enables import testing)

## Completion Status

**Task 2.1: COMPLETE ✅**

All acceptance criteria met. Function is ready for integration testing once boto3 dependency is added in Phase 3.
