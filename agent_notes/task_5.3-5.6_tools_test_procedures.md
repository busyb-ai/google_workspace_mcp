# Tasks 5.3-5.6: Google Workspace Tools Testing

## Overview

This document provides comprehensive testing procedures for all Google Workspace MCP tools, organized by service.

## Prerequisites

- OAuth authentication completed (Task 5.2)
- Valid credentials in S3 for test user
- Test Google account with sample data
- Service URL accessible: `http://google-workspace.busyb.local:8000`

## General Test Structure

Each tool test includes:
1. **Setup**: Prepare test data
2. **Execution**: Execute tool via MCP protocol
3. **Verification**: Verify results in Google Workspace interface
4. **Cleanup**: Clean up test data (if needed)

---

# Task 5.3: Gmail Tools Testing

## Test Environment Setup

### Create Test Gmail Data

```bash
# Use Gmail web interface to:
# 1. Send 5 test emails to yourself with subject "Test Email 1-5"
# 2. Create labels: "Important", "Work", "Personal"
# 3. Create a draft email
# 4. Have some unread messages
```

## Gmail Tool Tests

### Test 3.1: search_gmail_messages

**Objective**: Search for messages matching query

**Test Case 1: Search by Subject**
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

**Expected Result**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "messages": [
      {
        "id": "18d...",
        "threadId": "18d..."
      }
    ]
  }
}
```

**Verification**: Message IDs match test emails

**Test Case 2: Search Unread Messages**
```bash
# Query: "is:unread"
# Expected: List of unread message IDs
```

**Test Case 3: Search with Date Range**
```bash
# Query: "after:2025/01/01 before:2025/12/31"
# Expected: Messages in date range
```

---

### Test 3.2: get_gmail_message

**Objective**: Retrieve full message details by ID

```bash
# Get message ID from search_gmail_messages result
MESSAGE_ID="18d..."

curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_gmail_message",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "message_id": "'$MESSAGE_ID'"
      }
    }
  }'
```

**Expected Result**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "id": "18d...",
    "threadId": "18d...",
    "labelIds": ["INBOX", "UNREAD"],
    "snippet": "This is a test email...",
    "payload": {
      "headers": [
        {"name": "Subject", "value": "Test Email"},
        {"name": "From", "value": "sender@example.com"},
        {"name": "To", "value": "test@gmail.com"}
      ],
      "body": {...}
    }
  }
}
```

**Verification**:
- Message details match expected
- Subject, sender, recipient correct
- Body content present

---

### Test 3.3: send_gmail_message

**Objective**: Send email message

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "send_gmail_message",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "to": "test@gmail.com",
        "subject": "MCP Test Email",
        "body": "This is a test email sent via MCP"
      }
    }
  }'
```

**Expected Result**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "id": "18e...",
    "threadId": "18e...",
    "labelIds": ["SENT"]
  }
}
```

**Verification**:
- Check Gmail inbox for received email
- Subject and body match
- Email appears in Sent folder

---

### Test 3.4: list_gmail_labels

**Objective**: List user's Gmail labels

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_gmail_labels",
      "arguments": {
        "user_google_email": "test@gmail.com"
      }
    }
  }'
```

**Expected Result**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "labels": [
      {"id": "INBOX", "name": "INBOX", "type": "system"},
      {"id": "SENT", "name": "SENT", "type": "system"},
      {"id": "Label_123", "name": "Important", "type": "user"}
    ]
  }
}
```

**Verification**: Expected labels present (INBOX, SENT, custom labels)

---

### Test 3.5: create_gmail_draft

**Objective**: Create draft message

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_gmail_draft",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "to": "recipient@example.com",
        "subject": "Draft Email",
        "body": "This is a draft email"
      }
    }
  }'
```

**Verification**: Check Gmail Drafts folder for new draft

---

### Test 3.6: modify_gmail_message

**Objective**: Change message labels (mark as read/unread, add labels)

**Mark as Read**:
```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "modify_gmail_message",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "message_id": "'$MESSAGE_ID'",
        "remove_labels": ["UNREAD"]
      }
    }
  }'
```

**Verification**: Message shows as read in Gmail

---

## Gmail Test Checklist

- [ ] search_gmail_messages - by subject
- [ ] search_gmail_messages - unread messages
- [ ] search_gmail_messages - date range
- [ ] get_gmail_message - retrieve full message
- [ ] send_gmail_message - send email
- [ ] list_gmail_labels - list all labels
- [ ] create_gmail_draft - create draft
- [ ] modify_gmail_message - mark as read
- [ ] modify_gmail_message - add label
- [ ] delete_gmail_message - delete message
- [ ] Test with attachments (if supported)
- [ ] Test with HTML email (if supported)
- [ ] Test error handling (invalid message ID)

---

# Task 5.4: Google Drive Tools Testing

## Test Environment Setup

### Create Test Drive Data

```bash
# Use Google Drive web interface to:
# 1. Create folder "MCP Test Folder"
# 2. Upload 3 test files: document.pdf, image.jpg, data.csv
# 3. Create Google Doc "Test Document"
# 4. Create subfolder "Subfolder"
# 5. Share one file with test permissions
```

## Drive Tool Tests

### Test 4.1: list_drive_files

**Objective**: List files in Drive

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_drive_files",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "max_results": 10
      }
    }
  }'
```

**Expected Result**:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "files": [
      {
        "id": "1abc...",
        "name": "Test Document",
        "mimeType": "application/vnd.google-apps.document"
      }
    ]
  }
}
```

**Verification**: Expected files present in result

---

### Test 4.2: get_drive_file_metadata

**Objective**: Get file details

```bash
FILE_ID="1abc..."

curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_drive_file_metadata",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "file_id": "'$FILE_ID'"
      }
    }
  }'
```

**Expected Result**: File metadata with name, mimeType, size, createdTime, modifiedTime

---

### Test 4.3: download_drive_file

**Objective**: Download file content

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "download_drive_file",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "file_id": "'$FILE_ID'"
      }
    }
  }'
```

**Expected Result**: File content (base64 encoded or direct)

**Verification**: Downloaded content matches original file

---

### Test 4.4: upload_drive_file

**Objective**: Upload new file

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "upload_drive_file",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "file_name": "uploaded-test.txt",
        "file_content": "VGhpcyBpcyBhIHRlc3QgZmlsZQ==",
        "mime_type": "text/plain"
      }
    }
  }'
```

**Verification**: File appears in Drive with correct name and content

---

### Test 4.5: create_drive_folder

**Objective**: Create new folder

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_drive_folder",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "folder_name": "MCP Created Folder"
      }
    }
  }'
```

**Verification**: Folder created in Drive

---

### Test 4.6: move_drive_file

**Objective**: Move file to different folder

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "move_drive_file",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "file_id": "'$FILE_ID'",
        "new_parent_id": "'$FOLDER_ID'"
      }
    }
  }'
```

**Verification**: File moved to target folder in Drive

---

### Test 4.7: share_drive_file

**Objective**: Update file permissions

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "share_drive_file",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "file_id": "'$FILE_ID'",
        "email": "collaborator@example.com",
        "role": "reader"
      }
    }
  }'
```

**Verification**: File permissions updated in Drive

---

### Test 4.8: search_drive_files

**Objective**: Search files by query

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_drive_files",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "query": "name contains '\''test'\''"
      }
    }
  }'
```

**Verification**: Search returns matching files

---

## Drive Test Checklist

- [ ] list_drive_files - list recent files
- [ ] get_drive_file_metadata - get file details
- [ ] download_drive_file - download file content
- [ ] upload_drive_file - upload new file
- [ ] create_drive_folder - create folder
- [ ] move_drive_file - move to folder
- [ ] share_drive_file - update permissions
- [ ] search_drive_files - search by name
- [ ] search_drive_files - search by type
- [ ] delete_drive_file - delete file
- [ ] Test with large files (up to 10MB)
- [ ] Test with various file types (PDF, image, doc)
- [ ] Test error handling (invalid file ID)

---

# Task 5.5: Google Calendar Tools Testing

## Test Environment Setup

### Create Test Calendar Data

```bash
# Use Google Calendar web interface to:
# 1. Create calendar "MCP Test Calendar"
# 2. Create 3 test events with different dates
# 3. Create recurring event
# 4. Create event with attendees
```

## Calendar Tool Tests

### Test 5.1: list_calendars

**Objective**: List user's calendars

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_calendars",
      "arguments": {
        "user_google_email": "test@gmail.com"
      }
    }
  }'
```

**Expected Result**: List of calendars including primary and custom

---

### Test 5.2: list_calendar_events

**Objective**: List events in date range

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_calendar_events",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "time_min": "2025-01-01T00:00:00Z",
        "time_max": "2025-12-31T23:59:59Z",
        "max_results": 10
      }
    }
  }'
```

**Expected Result**: List of events in date range

---

### Test 5.3: get_calendar_event

**Objective**: Get specific event details

```bash
EVENT_ID="abc123..."

curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_calendar_event",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "event_id": "'$EVENT_ID'"
      }
    }
  }'
```

**Expected Result**: Event details with summary, start, end, attendees

---

### Test 5.4: create_calendar_event

**Objective**: Create new calendar event

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_calendar_event",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "summary": "MCP Test Meeting",
        "start_time": "2025-02-01T10:00:00-05:00",
        "end_time": "2025-02-01T11:00:00-05:00",
        "description": "Test event created via MCP"
      }
    }
  }'
```

**Verification**: Event appears in Google Calendar

---

### Test 5.5: update_calendar_event

**Objective**: Update existing event

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "update_calendar_event",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "event_id": "'$EVENT_ID'",
        "summary": "Updated Test Meeting",
        "start_time": "2025-02-01T14:00:00-05:00",
        "end_time": "2025-02-01T15:00:00-05:00"
      }
    }
  }'
```

**Verification**: Event updated in Calendar

---

### Test 5.6: delete_calendar_event

**Objective**: Delete event

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "delete_calendar_event",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "event_id": "'$EVENT_ID'"
      }
    }
  }'
```

**Verification**: Event removed from Calendar

---

### Test 5.7: search_calendar_events

**Objective**: Search events by query

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_calendar_events",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "query": "meeting"
      }
    }
  }'
```

**Verification**: Search returns matching events

---

## Calendar Test Checklist

- [ ] list_calendars - list all calendars
- [ ] list_calendar_events - list events in range
- [ ] get_calendar_event - get event details
- [ ] create_calendar_event - create simple event
- [ ] create_calendar_event - event with attendees
- [ ] create_calendar_event - recurring event
- [ ] update_calendar_event - update event time
- [ ] update_calendar_event - update attendees
- [ ] delete_calendar_event - delete event
- [ ] search_calendar_events - search by text
- [ ] Test all-day events
- [ ] Test events with reminders
- [ ] Test error handling (invalid event ID)

---

# Task 5.6: Other Google Workspace Tools Testing

## Google Docs Tools

### Test 6.1: create_google_doc

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_google_doc",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "title": "MCP Test Document"
      }
    }
  }'
```

### Test 6.2: get_google_doc_content

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_google_doc_content",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "document_id": "'$DOC_ID'"
      }
    }
  }'
```

### Test 6.3: update_google_doc

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "update_google_doc",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "document_id": "'$DOC_ID'",
        "text": "This is test content added via MCP"
      }
    }
  }'
```

---

## Google Sheets Tools

### Test 6.4: create_google_sheet

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_google_sheet",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "title": "MCP Test Spreadsheet"
      }
    }
  }'
```

### Test 6.5: read_sheet_values

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "read_sheet_values",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "spreadsheet_id": "'$SHEET_ID'",
        "range": "Sheet1!A1:D10"
      }
    }
  }'
```

### Test 6.6: update_sheet_values

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "update_sheet_values",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "spreadsheet_id": "'$SHEET_ID'",
        "range": "Sheet1!A1:B2",
        "values": [["Name", "Value"], ["Test", "123"]]
      }
    }
  }'
```

---

## Google Slides Tools

### Test 6.7: create_google_presentation

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_google_presentation",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "title": "MCP Test Presentation"
      }
    }
  }'
```

### Test 6.8: get_presentation_content

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_presentation_content",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "presentation_id": "'$PRES_ID'"
      }
    }
  }'
```

---

## Google Forms Tools

### Test 6.9: list_google_forms

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_google_forms",
      "arguments": {
        "user_google_email": "test@gmail.com"
      }
    }
  }'
```

### Test 6.10: get_form_responses

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "get_form_responses",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "form_id": "'$FORM_ID'"
      }
    }
  }'
```

---

## Google Tasks Tools

### Test 6.11: list_task_lists

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_task_lists",
      "arguments": {
        "user_google_email": "test@gmail.com"
      }
    }
  }'
```

### Test 6.12: create_task

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "create_task",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "task_list_id": "@default",
        "title": "MCP Test Task",
        "notes": "Created via MCP"
      }
    }
  }'
```

### Test 6.13: update_task

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "update_task",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "task_list_id": "@default",
        "task_id": "'$TASK_ID'",
        "status": "completed"
      }
    }
  }'
```

---

## Google Custom Search Tools

### Test 6.14: google_search

```bash
curl -X POST http://google-workspace.busyb.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "google_search",
      "arguments": {
        "user_google_email": "test@gmail.com",
        "query": "Google Workspace MCP",
        "num_results": 5
      }
    }
  }'
```

---

## Other Tools Test Checklist

### Docs
- [ ] create_google_doc
- [ ] get_google_doc_content
- [ ] update_google_doc
- [ ] insert_text_at_location
- [ ] apply_formatting

### Sheets
- [ ] create_google_sheet
- [ ] read_sheet_values
- [ ] update_sheet_values
- [ ] append_sheet_rows
- [ ] create_sheet_chart

### Slides
- [ ] create_google_presentation
- [ ] get_presentation_content
- [ ] add_slide
- [ ] update_slide_content

### Forms
- [ ] list_google_forms
- [ ] get_form_structure
- [ ] get_form_responses

### Tasks
- [ ] list_task_lists
- [ ] list_tasks
- [ ] create_task
- [ ] update_task
- [ ] complete_task
- [ ] delete_task

### Custom Search
- [ ] google_search - basic query
- [ ] google_search - with filters

---

## Overall Test Summary Template

```markdown
# Google Workspace Tools Test Summary

**Date**: YYYY-MM-DD
**Environment**: Production
**Service Version**: X.X.X
**Tester**: Name

## Test Statistics

| Service | Total Tests | Passed | Failed | Skipped | Pass Rate |
|---------|------------|--------|--------|---------|-----------|
| Gmail | 13 | 12 | 1 | 0 | 92% |
| Drive | 13 | 13 | 0 | 0 | 100% |
| Calendar | 10 | 10 | 0 | 0 | 100% |
| Docs | 5 | 4 | 1 | 0 | 80% |
| Sheets | 5 | 5 | 0 | 0 | 100% |
| Slides | 3 | 3 | 0 | 0 | 100% |
| Forms | 3 | 2 | 0 | 1 | 67% |
| Tasks | 6 | 6 | 0 | 0 | 100% |
| Search | 2 | 2 | 0 | 0 | 100% |
| **TOTAL** | **60** | **57** | **2** | **1** | **95%** |

## Critical Findings

### High Priority Issues
1. [Issue description]
   - Tool: [name]
   - Error: [details]
   - Impact: [description]
   - Fix required: Yes

### Medium Priority Issues
[List issues]

### Low Priority Issues
[List issues]

## Performance Observations

- Average response time: X ms
- Slowest tools: [list]
- Fastest tools: [list]
- Memory usage: X MB
- CPU usage: X%

## Recommendations

1. [Recommendation 1]
2. [Recommendation 2]
3. [Recommendation 3]

## Sign-off

- Tested by: [Name]
- Approved by: [Name]
- Date: YYYY-MM-DD
```

---

## Automated Test Script

```bash
#!/bin/bash
# workspace-tools-test.sh - Test all Google Workspace tools

SERVICE_URL="http://google-workspace.busyb.local:8000"
TEST_EMAIL="test@gmail.com"

# Track results
TOTAL=0
PASSED=0
FAILED=0

test_tool() {
  local tool_name=$1
  local json_payload=$2

  echo "Testing $tool_name..."
  TOTAL=$((TOTAL+1))

  response=$(curl -s -X POST "$SERVICE_URL/mcp" \
    -H "Content-Type: application/json" \
    -d "$json_payload")

  if echo "$response" | grep -q '"result"'; then
    echo "✅ $tool_name PASSED"
    PASSED=$((PASSED+1))
  else
    echo "❌ $tool_name FAILED"
    echo "Response: $response"
    FAILED=$((FAILED+1))
  fi
  echo ""
}

echo "=== Google Workspace Tools Test Suite ==="
echo ""

# Gmail tests
test_tool "search_gmail_messages" '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_gmail_messages",
    "arguments": {
      "user_google_email": "'$TEST_EMAIL'",
      "query": "subject:test"
    }
  }
}'

test_tool "list_gmail_labels" '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_gmail_labels",
    "arguments": {
      "user_google_email": "'$TEST_EMAIL'"
    }
  }
}'

# Drive tests
test_tool "list_drive_files" '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_drive_files",
    "arguments": {
      "user_google_email": "'$TEST_EMAIL'",
      "max_results": 10
    }
  }
}'

# Calendar tests
test_tool "list_calendars" '{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "list_calendars",
    "arguments": {
      "user_google_email": "'$TEST_EMAIL'"
    }
  }
}'

# Add more tests for other services...

echo "=== Test Results ==="
echo "Total: $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Pass Rate: $((PASSED * 100 / TOTAL))%"

if [ $FAILED -eq 0 ]; then
  echo "✅ All tests passed!"
  exit 0
else
  echo "❌ Some tests failed"
  exit 1
fi
```

---

## Next Steps

1. Complete OAuth authentication testing (Task 5.2)
2. Execute all Gmail tool tests
3. Execute all Drive tool tests
4. Execute all Calendar tool tests
5. Execute tests for remaining services
6. Document all results
7. Fix any critical issues found
8. Proceed to Task 5.7: CI/CD Pipeline Testing
