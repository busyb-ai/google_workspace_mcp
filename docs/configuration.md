# Configuration

This document covers all configuration options for the Google Workspace MCP Server.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Server Configuration](#server-configuration)
- [OAuth Configuration](#oauth-configuration)
- [S3 Credential Storage](#s3-credential-storage)
- [Deployment Options](#deployment-options)
- [Claude Desktop Integration](#claude-desktop-integration)

## Environment Variables

### Required Variables

#### `GOOGLE_OAUTH_CLIENT_ID`

Google OAuth client ID from Google Cloud Console.

- **Format**: `your-client-id.apps.googleusercontent.com`
- **Where to get**: Google Cloud Console → APIs & Services → Credentials
- **Example**: `123456789-abcdefg.apps.googleusercontent.com`

```bash
export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
```

#### `GOOGLE_OAUTH_CLIENT_SECRET`

Google OAuth client secret from Google Cloud Console.

- **Format**: String of alphanumeric characters
- **Where to get**: Google Cloud Console → APIs & Services → Credentials
- **Security**: Never commit this to version control

```bash
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

### Optional Variables

#### `WORKSPACE_MCP_PORT`

Port the server listens on.

- **Default**: `8000`
- **Type**: Integer
- **Affects**: Server binding, OAuth redirect URI

```bash
export WORKSPACE_MCP_PORT=8080
```

#### `WORKSPACE_MCP_BASE_URI`

Base URI for the server.

- **Default**: `http://localhost`
- **Type**: URL without trailing slash
- **Affects**: OAuth redirect URI construction

```bash
export WORKSPACE_MCP_BASE_URI="http://localhost"
# Or for production:
export WORKSPACE_MCP_BASE_URI="https://yourdomain.com"
```

#### `USER_GOOGLE_EMAIL`

Default email address for single-user setups.

- **Default**: None
- **Type**: Email address
- **Effect**: When set, LLM doesn't need to specify email in `start_google_auth`

```bash
export USER_GOOGLE_EMAIL="your-email@gmail.com"
```

#### `MCP_ENABLE_OAUTH21`

Enable OAuth 2.1 multi-user authentication.

- **Default**: `false`
- **Type**: Boolean (`true` or `false`)
- **Requires**: `streamable-http` transport mode

```bash
export MCP_ENABLE_OAUTH21=true
```

#### `MCP_SINGLE_USER_MODE`

Enable single-user mode (bypass session validation).

- **Default**: `0`
- **Type**: Boolean (`0` or `1`)
- **Effect**: Simplifies authentication for single-user scenarios

```bash
export MCP_SINGLE_USER_MODE=1
```

#### `GOOGLE_CLIENT_SECRET_PATH`

Path to `client_secret.json` file.

- **Default**: `./client_secret.json`
- **Type**: File path
- **Alternative**: Use `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` env vars instead

```bash
export GOOGLE_CLIENT_SECRET_PATH="/path/to/client_secret.json"
```

#### `GOOGLE_OAUTH_REDIRECT_URI`

Override for OAuth redirect URI.

- **Default**: Constructed from `WORKSPACE_MCP_BASE_URI` and `WORKSPACE_MCP_PORT`
- **Type**: Full URL including port
- **Warning**: Only use if you need separate OAuth redirect server

```bash
export GOOGLE_OAUTH_REDIRECT_URI="http://localhost:8000/oauth2callback"
```

#### `OAUTHLIB_INSECURE_TRANSPORT`

Allow OAuth over HTTP (development only).

- **Default**: Not set
- **Type**: Boolean (`1` to enable)
- **Security**: Only use in development, never in production

```bash
export OAUTHLIB_INSECURE_TRANSPORT=1
```

#### `GOOGLE_PSE_API_KEY`

Google Custom Search API key.

- **Default**: None
- **Type**: String
- **Required for**: Custom Search tools
- **Where to get**: Google Developers Console → API Key

```bash
export GOOGLE_PSE_API_KEY="your-custom-search-api-key"
```

#### `GOOGLE_PSE_ENGINE_ID`

Programmable Search Engine ID.

- **Default**: None
- **Type**: String (cx parameter)
- **Required for**: Custom Search tools
- **Where to get**: Programmable Search Engine Control Panel

```bash
export GOOGLE_PSE_ENGINE_ID="your-search-engine-id"
```

### Variable Loading Priority

Variables are loaded in this order (highest to lowest priority):

1. **Manually set environment variables**
   ```bash
   export GOOGLE_OAUTH_CLIENT_ID="..."
   ```

2. **Variables in `.env` file**
   ```
   GOOGLE_OAUTH_CLIENT_ID=...
   ```

3. **`client_secret.json` at custom path**
   ```bash
   export GOOGLE_CLIENT_SECRET_PATH="/path/to/client_secret.json"
   ```

4. **`client_secret.json` in project root**

## Server Configuration

### Transport Modes

#### stdio (Default)

Standard input/output mode for MCP clients.

**Use for**:
- Claude Desktop
- Other MCP-compatible clients
- Terminal-based interactions

**Characteristics**:
- No HTTP server (except minimal OAuth callback server)
- JSON-RPC over stdio
- Automatic OAuth callback server on port 8000

**Start command**:
```bash
uv run main.py
# Or explicitly:
uv run main.py --transport stdio
```

#### streamable-http

HTTP server mode with SSE (Server-Sent Events).

**Use for**:
- Web interfaces
- Debugging
- API integrations
- OAuth 2.1 multi-user mode

**Characteristics**:
- HTTP server on configured port
- SSE for real-time updates
- Full REST API
- OAuth callbacks handled by main server

**Start command**:
```bash
uv run main.py --transport streamable-http
```

### Tool Selection

Selectively enable tools to reduce scope requirements and improve startup time.

**Enable specific tools**:
```bash
uv run main.py --tools gmail drive calendar
```

**Available tools**:
- `gmail` - Gmail API integration
- `drive` - Google Drive API
- `calendar` - Google Calendar API
- `docs` - Google Docs API
- `sheets` - Google Sheets API
- `slides` - Google Slides API
- `forms` - Google Forms API
- `tasks` - Google Tasks API
- `chat` - Google Chat API
- `search` - Google Custom Search API

**Default**: All tools enabled if not specified

### Single-User Mode

Simplified authentication for single-user scenarios.

**Enable via CLI**:
```bash
uv run main.py --single-user
```

**Enable via environment**:
```bash
export MCP_SINGLE_USER_MODE=1
uv run main.py
```

**Effects**:
- Bypasses session validation
- Simplified credential management
- Useful for personal use or development

### Combining Options

All options can be combined:

```bash
uv run main.py \
  --transport streamable-http \
  --tools gmail drive calendar tasks \
  --single-user
```

## OAuth Configuration

### Google Cloud Console Setup

#### 1. Create OAuth Client

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth Client ID**
5. Choose **Web Application**
6. Add redirect URI: `http://localhost:8000/oauth2callback`

#### 2. Enable APIs

Enable the Google Workspace APIs you need:

- [Google Calendar API](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com)
- [Google Drive API](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com)
- [Gmail API](https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com)
- [Google Docs API](https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com)
- [Google Sheets API](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com)
- [Google Slides API](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com)
- [Google Forms API](https://console.cloud.google.com/flows/enableapi?apiid=forms.googleapis.com)
- [Google Tasks API](https://console.cloud.google.com/flows/enableapi?apiid=tasks.googleapis.com)
- [Google Chat API](https://console.cloud.google.com/flows/enableapi?apiid=chat.googleapis.com)
- [Google Custom Search API](https://console.cloud.google.com/flows/enableapi?apiid=customsearch.googleapis.com)

#### 3. Configure Credentials

**Option A: Environment Variables (Recommended)**

Create a `.env` file:
```bash
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
OAUTHLIB_INSECURE_TRANSPORT=1  # Development only
```

**Option B: File-Based**

Download `client_secret.json` from Google Cloud Console and place in project root:

```json
{
  "installed": {
    "client_id": "your-client-id.apps.googleusercontent.com",
    "client_secret": "your-client-secret",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "redirect_uris": ["http://localhost:8000/oauth2callback"]
  }
}
```

### OAuth Redirect URI

The OAuth redirect URI must match exactly what's configured in Google Cloud Console.

**Default**:
```
http://localhost:8000/oauth2callback
```

**For custom port**:
```bash
export WORKSPACE_MCP_PORT=8080
# Redirect URI becomes: http://localhost:8080/oauth2callback
# Update this in Google Cloud Console
```

**For production**:
```bash
export WORKSPACE_MCP_BASE_URI="https://yourdomain.com"
export WORKSPACE_MCP_PORT=443
# Redirect URI becomes: https://yourdomain.com/oauth2callback
# Update this in Google Cloud Console
```

### Scope Configuration

Scopes are automatically configured based on enabled tools. To customize:

1. Edit `auth/scopes.py` to add/modify scopes
2. Edit `auth/service_decorator.py` to add scope groups
3. Update `TOOL_SCOPES_MAP` to associate tools with scopes

## S3 Credential Storage

The Google Workspace MCP Server supports storing OAuth credentials in AWS S3 as an alternative to local file system storage. This enables centralized credential management across multiple server instances and provides enhanced security through AWS IAM and encryption.

### Overview

**Benefits of S3 Storage**:
- **Multi-server deployments**: Share credentials across multiple server instances
- **Centralized management**: Single source of truth for all credentials
- **Enhanced security**: AWS IAM-based access control and server-side encryption
- **Cloud-native**: No persistent local storage required
- **Automatic backups**: Leverage S3's durability and versioning capabilities

**Storage Locations**:
- **Local** (default): `.credentials/{email}.json` files on local file system
- **S3**: `s3://bucket-name/path/{email}.json` files in AWS S3

The server automatically detects which storage type to use based on the path prefix (`s3://` for S3, otherwise local).

### Configuration

#### Environment Variable

Set the `GOOGLE_MCP_CREDENTIALS_DIR` environment variable to an S3 path:

```bash
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket-name/credentials/"
```

**Path Format**:
- Must start with `s3://`
- Include bucket name: `s3://bucket-name/`
- Optional path prefix: `s3://bucket-name/path/to/credentials/`
- Trailing slash recommended but not required

**Examples**:
```bash
# Store in bucket root
export GOOGLE_MCP_CREDENTIALS_DIR="s3://workspace-mcp-credentials/"

# Store in subdirectory
export GOOGLE_MCP_CREDENTIALS_DIR="s3://my-company-bucket/mcp/credentials/"

# Environment-specific paths
export GOOGLE_MCP_CREDENTIALS_DIR="s3://my-bucket/prod/credentials/"
export GOOGLE_MCP_CREDENTIALS_DIR="s3://my-bucket/dev/credentials/"
```

### AWS Credentials

The S3 client uses the standard AWS credential chain to authenticate. Credentials are discovered in this order:

#### 1. Environment Variables (Recommended for Docker/CI)

```bash
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_REGION="us-east-1"  # Optional, defaults to us-east-1
```

**Docker Example**:
```bash
docker run -p 8000:8000 \
  -e GOOGLE_MCP_CREDENTIALS_DIR="s3://my-bucket/credentials/" \
  -e AWS_ACCESS_KEY_ID="your-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret" \
  -e AWS_REGION="us-east-1" \
  workspace-mcp --transport streamable-http
```

#### 2. IAM Roles (Recommended for Production)

When running on AWS infrastructure (EC2, ECS, Lambda), use IAM roles for automatic credential management:

**No credentials needed in environment** - AWS automatically provides credentials through instance metadata.

**Example IAM Policy** (attach to EC2 instance role, ECS task role, or Lambda execution role):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name/*",
        "arn:aws:s3:::your-bucket-name"
      ]
    }
  ]
}
```

**Required Permissions**:
- `s3:GetObject` - Read credential files
- `s3:PutObject` - Write credential files
- `s3:DeleteObject` - Delete credential files (for revocation)
- `s3:ListBucket` - List credential files (for single-user mode)

#### 3. AWS Credentials File (Local Development)

Create `~/.aws/credentials` file:

```ini
[default]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
region = us-east-1
```

**Or use named profiles**:
```ini
[workspace-mcp]
aws_access_key_id = your-access-key-id
aws_secret_access_key = your-secret-access-key
region = us-west-2
```

Then set the profile:
```bash
export AWS_PROFILE=workspace-mcp
```

### S3 Bucket Setup

#### Create S3 Bucket

```bash
# Set your bucket name and region
BUCKET_NAME="workspace-mcp-credentials"
AWS_REGION="us-east-1"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${AWS_REGION}
```

#### Enable Encryption (Recommended)

**Option 1: Server-Side Encryption with S3-Managed Keys (SSE-S3)**

Default encryption is automatically enabled by the server when uploading files. To enforce bucket-level encryption:

```bash
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'
```

**Option 2: Server-Side Encryption with AWS KMS (SSE-KMS)**

For additional key management and audit capabilities:

```bash
# Create KMS key
KMS_KEY_ID=$(aws kms create-key \
  --description "Workspace MCP Credentials Encryption" \
  --query 'KeyMetadata.KeyId' \
  --output text)

# Enable KMS encryption on bucket
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration "{
    \"Rules\": [{
      \"ApplyServerSideEncryptionByDefault\": {
        \"SSEAlgorithm\": \"aws:kms\",
        \"KMSMasterKeyID\": \"${KMS_KEY_ID}\"
      },
      \"BucketKeyEnabled\": true
    }]
  }"
```

#### Configure Private Access (Recommended)

Block all public access to ensure credentials remain private:

```bash
aws s3api put-public-access-block \
  --bucket ${BUCKET_NAME} \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

#### Enable Versioning (Optional)

Enable versioning to maintain history of credential changes:

```bash
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled
```

#### Set Lifecycle Policy (Optional)

Automatically delete old versions after a retention period:

```bash
cat > lifecycle-policy.json <<EOF
{
  "Rules": [{
    "Id": "DeleteOldVersions",
    "Status": "Enabled",
    "NoncurrentVersionExpiration": {
      "NoncurrentDays": 90
    }
  }]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket ${BUCKET_NAME} \
  --lifecycle-configuration file://lifecycle-policy.json
```

### Complete Setup Example

Here's a complete setup example for production use:

```bash
#!/bin/bash

# Configuration
BUCKET_NAME="workspace-mcp-credentials"
AWS_REGION="us-east-1"

# 1. Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${AWS_REGION}

# 2. Block public access
aws s3api put-public-access-block \
  --bucket ${BUCKET_NAME} \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# 3. Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

# 4. Enable versioning
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# 5. Configure lifecycle policy
cat > /tmp/lifecycle-policy.json <<EOF
{
  "Rules": [{
    "Id": "DeleteOldVersions",
    "Status": "Enabled",
    "NoncurrentVersionExpiration": {
      "NoncurrentDays": 90
    }
  }]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket ${BUCKET_NAME} \
  --lifecycle-configuration file:///tmp/lifecycle-policy.json

rm /tmp/lifecycle-policy.json

echo "S3 bucket ${BUCKET_NAME} configured successfully!"
echo "Set environment variable: export GOOGLE_MCP_CREDENTIALS_DIR=s3://${BUCKET_NAME}/"
```

### Using S3 Storage

Once configured, the server automatically uses S3 for all credential operations:

```bash
# Start server with S3 storage
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket/credentials/"
export AWS_REGION="us-east-1"

# With environment variables for AWS credentials
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

uv run main.py --transport streamable-http
```

**Or with IAM role** (no AWS credentials needed):
```bash
# On EC2/ECS/Lambda with proper IAM role
export GOOGLE_MCP_CREDENTIALS_DIR="s3://your-bucket/credentials/"
uv run main.py --transport streamable-http
```

**Credential files** are stored as:
- `s3://your-bucket/credentials/user@gmail.com.json`
- `s3://your-bucket/credentials/admin@example.com.json`
- etc.

### Migration from Local to S3

To migrate existing local credentials to S3:

```bash
# Set your bucket and local credentials directory
BUCKET_NAME="workspace-mcp-credentials"
LOCAL_CREDS_DIR=".credentials"

# Upload all credential files to S3
aws s3 sync ${LOCAL_CREDS_DIR}/ s3://${BUCKET_NAME}/ \
  --exclude "*" \
  --include "*.json" \
  --sse AES256

# Verify files were uploaded
aws s3 ls s3://${BUCKET_NAME}/

# Update environment variable
export GOOGLE_MCP_CREDENTIALS_DIR="s3://${BUCKET_NAME}/"

# Restart server
```

### Troubleshooting S3 Storage

#### Error: AWS credentials not found

**Symptom**:
```
NoCredentialsError: AWS credentials not found. Please configure credentials using one of these methods...
```

**Solutions**:
1. Set environment variables: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
2. Create `~/.aws/credentials` file with valid credentials
3. Ensure IAM role is attached to EC2/ECS/Lambda instance
4. Check `AWS_PROFILE` environment variable if using named profiles

#### Error: S3 bucket does not exist

**Symptom**:
```
NoSuchBucket: S3 bucket 'my-bucket' does not exist.
```

**Solutions**:
1. Verify bucket name is correct (no typos)
2. Verify bucket exists in the correct AWS region
3. Create bucket: `aws s3 mb s3://my-bucket --region us-east-1`
4. Check `AWS_REGION` environment variable matches bucket region

#### Error: Access denied

**Symptom**:
```
AccessDenied: Access denied to S3 bucket 'my-bucket'.
```

**Solutions**:
1. Check IAM user/role has required S3 permissions:
   - `s3:GetObject`
   - `s3:PutObject`
   - `s3:DeleteObject`
   - `s3:ListBucket`
2. Verify bucket policy doesn't deny access
3. Check bucket is not in a different AWS account
4. Ensure AWS credentials are for the correct AWS account

**Example IAM policy** to attach to user/role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::my-bucket/*"
    },
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::my-bucket"
    }
  ]
}
```

#### Error: Incomplete AWS credentials

**Symptom**:
```
PartialCredentialsError: Incomplete AWS credentials found.
```

**Solutions**:
1. Ensure both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are set
2. Check for typos in environment variable names
3. Verify credentials file has both `aws_access_key_id` and `aws_secret_access_key`

#### Error: Failed to parse JSON

**Symptom**:
```
ValueError: Failed to parse JSON from S3 file... The file may be corrupted.
```

**Solutions**:
1. Download file and verify it's valid JSON: `aws s3 cp s3://bucket/file.json - | python -m json.tool`
2. Delete corrupted file and reauthenticate: `aws s3 rm s3://bucket/file.json`
3. Check file wasn't partially written (network interruption during upload)

#### Slow performance

**Symptoms**:
- Slow authentication
- Delayed tool responses

**Solutions**:
1. Use S3 bucket in same AWS region as server
2. Verify network connectivity to S3
3. Check S3 service health: [AWS Status Dashboard](https://status.aws.amazon.com/)
4. Consider using S3 Transfer Acceleration for cross-region deployments
5. Ensure S3 client caching is working (check logs for "Initialized S3 client" message)

#### Network errors

**Symptom**:
```
EndpointConnectionError: Could not connect to the endpoint URL
```

**Solutions**:
1. Check internet connectivity
2. Verify firewall/security group allows HTTPS (443) to S3 endpoints
3. Check VPC endpoints if using private subnets
4. Verify DNS resolution for S3 endpoints: `nslookup s3.amazonaws.com`
5. Check proxy settings if behind corporate proxy

### Security Best Practices

1. **Use IAM roles** instead of access keys when running on AWS infrastructure
2. **Enable bucket encryption** (SSE-S3 or SSE-KMS) for data at rest
3. **Block public access** to ensure credentials remain private
4. **Use private buckets** - never make credential buckets public
5. **Enable versioning** to maintain audit trail of changes
6. **Rotate credentials** regularly and update S3 files accordingly
7. **Use bucket policies** to restrict access by IP or VPC if needed
8. **Enable CloudTrail** to audit all S3 access for compliance
9. **Set lifecycle policies** to automatically delete old credential versions
10. **Use separate buckets** for different environments (dev, staging, prod)

### Cost Considerations

S3 storage for credentials is very cost-effective:

- **Storage**: ~$0.023 per GB per month (S3 Standard)
- **Requests**:
  - PUT/POST: $0.005 per 1,000 requests
  - GET: $0.0004 per 1,000 requests
- **Data transfer**: Free for same-region transfers

**Example cost** for 100 users:
- Storage: 100 files × 2KB = 200KB ≈ $0.00001/month
- Requests: ~10,000 requests/month ≈ $0.05/month
- **Total**: < $0.10/month

**Cost optimization**:
- Use S3 Standard-IA (Infrequent Access) if credentials are rarely updated
- Enable S3 Intelligent-Tiering for automatic cost optimization
- Set lifecycle policies to delete old versions

## Deployment Options

### Local Development

```bash
# 1. Clone repository
git clone https://github.com/taylorwilsdon/google_workspace_mcp.git
cd google_workspace_mcp

# 2. Install dependencies
uv sync

# 3. Create .env file
cp .env.oauth21 .env
# Edit .env with your credentials

# 4. Run server
uv run main.py
```

### Docker Deployment

#### Build Image

```bash
docker build -t workspace-mcp .
```

#### Run Container

**With environment variables**:
```bash
docker run -p 8000:8000 \
  -e GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  -e OAUTHLIB_INSECURE_TRANSPORT=1 \
  workspace-mcp --transport streamable-http
```

**With .env file**:
```bash
docker run -p 8000:8000 \
  --env-file .env \
  workspace-mcp --transport streamable-http
```

**With volume for credentials**:
```bash
docker run -p 8000:8000 \
  -v $(pwd)/.credentials:/app/.credentials \
  -e GOOGLE_OAUTH_CLIENT_ID="your-client-id" \
  -e GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret" \
  workspace-mcp --transport streamable-http
```

#### Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  workspace-mcp:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
      - GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}
      - MCP_ENABLE_OAUTH21=true
      - WORKSPACE_MCP_BASE_URI=http://localhost
      - WORKSPACE_MCP_PORT=8000
    volumes:
      - ./.credentials:/app/.credentials
    command: ["--transport", "streamable-http"]
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

### Cloud Deployment

#### Heroku

1. **Create Heroku app**:
```bash
heroku create your-app-name
```

2. **Set environment variables**:
```bash
heroku config:set GOOGLE_OAUTH_CLIENT_ID="your-client-id"
heroku config:set GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
heroku config:set WORKSPACE_MCP_BASE_URI="https://your-app-name.herokuapp.com"
```

3. **Deploy**:
```bash
git push heroku main
```

#### Railway

1. **Connect repository**
2. **Set environment variables** in Railway dashboard
3. **Configure start command**: `uv run main.py --transport streamable-http`
4. **Deploy**

#### DigitalOcean App Platform

1. **Create new app** from GitHub repository
2. **Set environment variables**
3. **Configure run command**: `uv run main.py --transport streamable-http`
4. **Deploy**

### Production Considerations

#### HTTPS

Always use HTTPS in production:

```bash
export WORKSPACE_MCP_BASE_URI="https://yourdomain.com"
export WORKSPACE_MCP_PORT=443
# Remove or set to 0:
export OAUTHLIB_INSECURE_TRANSPORT=0
```

Update redirect URI in Google Cloud Console:
```
https://yourdomain.com/oauth2callback
```

#### Reverse Proxy

Use nginx or similar for SSL termination:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

#### Process Management

Use systemd, supervisor, or PM2:

**systemd service** (`/etc/systemd/system/workspace-mcp.service`):
```ini
[Unit]
Description=Google Workspace MCP Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/workspace-mcp
Environment="GOOGLE_OAUTH_CLIENT_ID=your-client-id"
Environment="GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret"
Environment="WORKSPACE_MCP_BASE_URI=https://yourdomain.com"
ExecStart=/usr/local/bin/uv run main.py --transport streamable-http
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable workspace-mcp
sudo systemctl start workspace-mcp
```

## Claude Desktop Integration

### Installation Methods

#### Method 1: DXT (Recommended)

1. Download latest `.dxt` file from releases
2. Double-click to install in Claude Desktop
3. Configure credentials in Claude Desktop settings
4. Start using tools

#### Method 2: Automatic Script

```bash
python install_claude.py
```

Follow prompts to enter credentials.

#### Method 3: Manual Configuration

**macOS**: Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows**: Edit `%APPDATA%\Claude\claude_desktop_config.json`

**Configuration**:

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "uvx",
      "args": ["workspace-mcp"],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "your-client-secret",
        "OAUTHLIB_INSECURE_TRANSPORT": "1"
      }
    }
  }
}
```

**For development**:

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/google_workspace_mcp",
        "main.py"
      ],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "your-client-secret",
        "OAUTHLIB_INSECURE_TRANSPORT": "1"
      }
    }
  }
}
```

### Selective Tool Configuration

Enable only specific tools in Claude Desktop:

```json
{
  "mcpServers": {
    "google_workspace": {
      "command": "uvx",
      "args": [
        "workspace-mcp",
        "--tools",
        "gmail",
        "calendar",
        "drive"
      ],
      "env": {
        "GOOGLE_OAUTH_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
        "GOOGLE_OAUTH_CLIENT_SECRET": "your-client-secret",
        "OAUTHLIB_INSECURE_TRANSPORT": "1"
      }
    }
  }
}
```

### Troubleshooting Claude Desktop

#### Server Not Starting

Check logs:
- **macOS**: `~/Library/Logs/Claude/mcp*.log`
- **Windows**: `%APPDATA%\Claude\logs\mcp*.log`

Common issues:
- Invalid JSON in config file
- Missing credentials
- Port already in use
- `uvx` not installed

#### Authentication Not Working

1. Check credentials are correct
2. Verify redirect URI: `http://localhost:8000/oauth2callback`
3. Ensure APIs are enabled in Google Cloud Console
4. Check `OAUTHLIB_INSECURE_TRANSPORT=1` is set

#### Tools Not Appearing

1. Restart Claude Desktop
2. Check MCP server is running (look for process)
3. Verify config JSON syntax
4. Check server logs for errors
