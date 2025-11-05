# Task 2.2 Summary: Update save_credentials_to_file() for S3 Support

## Task Overview
**Task ID:** 2.2
**Phase:** 2 - Update Credential Functions
**Status:** ✅ COMPLETED
**Date:** 2025-10-21

## Objective
Update the `save_credentials_to_file()` function in `auth/google_auth.py` to support saving credentials to AWS S3 in addition to local file storage.

## Changes Made

### 1. Import Updates
**File:** `auth/google_auth.py` (line 20)

**Before:**
```python
from auth.s3_storage import is_s3_path
```

**After:**
```python
from auth.s3_storage import is_s3_path, s3_upload_json
```

**Rationale:** Added `s3_upload_json` import to enable S3 upload functionality.

---

### 2. Function Implementation Updates
**File:** `auth/google_auth.py` (lines 161-209)

#### Updated Docstring
**Before:**
```python
"""Saves user credentials to a file."""
```

**After:**
```python
"""
Saves user credentials to a file or S3.

Supports both local file storage and AWS S3 storage. Storage location is determined
by the base_dir path format:
- Local: /path/to/credentials/
- S3: s3://bucket-name/path/

Args:
    user_google_email: User's Google email address
    credentials: Google OAuth credentials object
    base_dir: Base directory path (local or S3)

Raises:
    IOError: If local file write fails
    ClientError: If S3 upload fails
    Exception: For other errors during credential save
"""
```

**Rationale:** Enhanced docstring to document S3 support, explain both storage types, and document error conditions.

#### Updated Implementation Logic
**Before:**
```python
try:
    with open(creds_path, "w") as f:
        json.dump(creds_data, f)
    logger.info(f"Credentials saved for user {user_google_email} to {creds_path}")
except IOError as e:
    logger.error(
        f"Error saving credentials for user {user_google_email} to {creds_path}: {e}"
    )
    raise
```

**After:**
```python
try:
    if is_s3_path(creds_path):
        # Upload to S3
        s3_upload_json(creds_path, creds_data)
        logger.info(f"Credentials saved for user {user_google_email} to S3: {creds_path}")
    else:
        # Save to local file (existing logic)
        with open(creds_path, "w") as f:
            json.dump(creds_data, f)
        logger.info(f"Credentials saved for user {user_google_email} to {creds_path}")
except Exception as e:
    logger.error(
        f"Error saving credentials for user {user_google_email} to {creds_path}: {e}"
    )
    raise
```

**Key Changes:**
1. Added S3 path detection using `is_s3_path(creds_path)`
2. Added S3 upload branch that calls `s3_upload_json(creds_path, creds_data)`
3. Preserved local file save logic in else branch
4. Updated log message for S3 saves to explicitly mention "S3" for clarity
5. Changed exception type from `IOError` to generic `Exception` to handle both storage types

## Implementation Details

### Credential Data Format
The credential data serialization logic remains **unchanged** - both local and S3 storage use the same format:
```python
creds_data = {
    "token": credentials.token,
    "refresh_token": credentials.refresh_token,
    "token_uri": credentials.token_uri,
    "client_id": credentials.client_id,
    "client_secret": credentials.client_secret,
    "scopes": credentials.scopes,
    "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
}
```

### Storage Path Detection
The function uses `is_s3_path()` from `auth.s3_storage` to determine storage type:
- **S3 path:** Starts with `s3://` → uses `s3_upload_json()`
- **Local path:** All other paths → uses traditional file I/O

### Error Handling
- S3 upload errors from `s3_upload_json()` propagate naturally through the try/except block
- Local file errors continue to be caught as before
- Both storage types produce clear, actionable error messages via logging
- Error logging includes the full path for debugging

### Logging Enhancement
- **S3 saves:** Log message explicitly mentions "to S3: {path}" for clarity
- **Local saves:** Retains original log message format
- This distinction helps operators understand where credentials are being stored

## Acceptance Criteria Verification

✅ **Function saves to S3 when given S3 path**
- Implementation checks `is_s3_path()` and calls `s3_upload_json()`

✅ **Function saves to local file when given local path**
- Original file write logic preserved in else branch

✅ **Credential data format unchanged**
- `creds_data` dictionary construction is identical to original

✅ **Logging clearly indicates S3 vs local storage**
- S3 log: "Credentials saved for user {email} to S3: {path}"
- Local log: "Credentials saved for user {email} to {path}"

✅ **Error handling covers both storage types**
- Generic `Exception` catch handles both `IOError` (local) and S3 errors
- Error logging works for both paths

✅ **Docstring updated to mention S3 support**
- Comprehensive docstring documents both storage types
- Includes path format examples
- Documents all exceptions

✅ **No changes to function signature**
- Signature remains: `save_credentials_to_file(user_google_email, credentials, base_dir)`

✅ **Backward compatible - local storage still works**
- Original local file logic completely preserved
- Only modification is wrapping in `else` branch
- No breaking changes

## Testing Recommendations

### Unit Tests
1. **Test S3 save:** Mock `is_s3_path()` to return True, verify `s3_upload_json()` called
2. **Test local save:** Mock `is_s3_path()` to return False, verify file write occurs
3. **Test error handling:** Verify both S3 and local errors are caught and logged
4. **Test credential format:** Verify `creds_data` structure matches expected format

### Integration Tests
1. **Test with real S3:** Save credentials to actual S3 bucket
2. **Test with local filesystem:** Save credentials to local directory
3. **Test path switching:** Verify switching between storage types works seamlessly
4. **Test OAuth 2.1 flow:** Verify S3 storage works with OAuth 2.1 authentication

## Dependencies
- **Imports:** `is_s3_path` and `s3_upload_json` from `auth.s3_storage`
- **Required for S3:** `boto3` library (added in Task 3.1)
- **Prerequisites:** Task 2.1 completed (`_get_user_credential_path()` updated)

## Related Tasks
- **Task 2.1:** Updated `_get_user_credential_path()` for S3 support (dependency)
- **Task 2.3:** Update `load_credentials_from_file()` for S3 support (next task)
- **Task 2.4:** Update `_find_any_credentials()` for S3 support
- **Task 3.1:** Add boto3 dependency to pyproject.toml

## Files Modified
- ✏️ `auth/google_auth.py` (lines 20, 161-209)

## Lines of Code Changed
- **Added:** ~20 lines (docstring, S3 branch, enhanced logging)
- **Modified:** ~5 lines (imports, exception type, logging)
- **Total Impact:** ~25 lines

## Backward Compatibility
✅ **100% Backward Compatible**
- All existing local file storage code preserved
- No changes to function signature or parameters
- Existing callers will continue to work without modification
- Local storage behavior unchanged

## Notes
- The function automatically detects storage type based on the `base_dir` path
- No explicit configuration needed - S3 vs local is determined by path prefix
- S3 credentials saved with server-side encryption (SSE-S3) via `s3_upload_json()`
- Error messages from `s3_upload_json()` will include helpful AWS troubleshooting info
