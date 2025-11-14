# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a production-ready MCP (Model Context Protocol) server providing comprehensive Google Workspace integration for AI assistants. Built with FastMCP, it supports both single-user and multi-user OAuth 2.1 authentication across all major Google Workspace services: Gmail, Drive, Calendar, Docs, Sheets, Slides, Forms, Tasks, Chat, and Custom Search.

**Key Architecture**: Service Decorator Pattern with automatic OAuth handling, 30-minute service caching, and transport-aware authentication (stdio for MCP clients, streamable-http for web interfaces).

**Published as**: `workspace-mcp` on PyPI with Desktop Extension (.dxt) support for one-click Claude Desktop installation.

## Main Documentation

Detailed documentation is organized in the `docs/` folder:

- **@docs/architecture.md** - Core design patterns, authentication flows, and module interactions
- **@docs/development.md** - Development guide including adding new tools, testing, and debugging
- **@docs/authentication.md** - OAuth 2.0/2.1 implementation details and credential management
- **@docs/configuration.md** - Environment variables, server configuration, and deployment options
- **@docs/api-reference.md** - Tool structure, decorators, and service integration patterns

## Core Concepts

### Service Decorator Pattern
The `@require_google_service(service_type, scopes)` decorator automatically handles authentication, service injection, and caching:

```python
@server.tool()
@require_google_service("gmail", "gmail_read")
async def search_gmail(service, user_google_email: str, query: str):
    # service is authenticated and injected automatically
    return service.users().messages().list(userId='me', q=query).execute()
```

### Authentication Modes
- **Legacy OAuth 2.0**: File-based credentials (`.credentials/{email}.json`), tool-based auth flow
- **OAuth 2.1**: Bearer token authentication with multi-user session management, CORS proxy for browser clients

### Credential Storage Options
Credentials can be stored in two locations:
- **Local File System**: Default `.credentials/{email}.json` directory
- **AWS S3**: Using `s3://bucket/path/` format (requires boto3 dependency)

The `auth/s3_storage.py` module provides S3 abstraction with automatic path detection via `s3://` prefix.

### Transport-Aware OAuth
- **stdio mode**: Launches minimal HTTP server on port 8000 for OAuth callbacks
- **streamable-http mode**: Uses main FastAPI server for callbacks
- Both use `http://localhost:8000/oauth2callback` for consistency

## File Structure

```
google_workspace_mcp/
├── auth/              # Authentication system (decorators, OAuth, session management, S3 storage)
├── core/              # MCP server instance, configuration, utilities
├── g{service}/        # Service-specific tools (gmail/, gdrive/, gcalendar/, etc.)
├── main.py            # Entry point with CLI argument parsing
├── pyproject.toml     # Package configuration and dependencies
├── .credentials/      # Auto-created for local OAuth credential storage
└── docs/              # Detailed documentation
```

## Common Issues

- **OAuth callback 404**: Transport mode must be set before auth flow starts
- **Scope errors**: Verify scopes exist in `SCOPE_GROUPS` and tool is in `TOOL_SCOPES_MAP`
- **Token refresh errors**: Credentials expired/revoked, reauthenticate with `start_google_auth`
- **Import errors**: Tool module must be imported in `main.py`'s `tool_imports` dict

## Debugging

- Logs: `mcp_server_debug.log` in project root
- Health check: `GET /health` endpoint
- Session tracing: Look for "Auth from middleware" and "MCPSessionID" in logs

---

## Rules for Claude Code

### Code Quality and Standards

1. **Follow existing patterns**: Use the `@require_google_service()` decorator pattern for all new tools
2. **First parameter must be `service`**: This is injected by the decorator and hidden from FastMCP
3. **Second parameter must be `user_google_email: str`**: Required for authentication
4. **Use scope groups**: Reference scopes by friendly names (e.g., "gmail_read") defined in `SCOPE_GROUPS`
5. **Error handling**: Use `@handle_http_errors()` decorator for HTTP error handling
6. **Logging**: Use module-level loggers: `logger = logging.getLogger(__name__)`


When working with code in this repository, please adhere to the following rules:
1. When creating a new feature, refactoring, or otherwise modifying code, always ensure that you are in a git worktree that is not the main tree.
   - If you are continuing work on a plan that has already started, you should continue on the branch for that plan.
   - If you are starting a new plan and not already in a worktree, create a new branch from `main` with a descriptive name for the feature or fix you are working on, and make sure to move the working directory to that branch.
2. Ensure that all new code is well-documented with docstrings and comments where necessary.
3. Do not over-engineer solutions. Keep things as simple as possible while still meeting requirements.
4. Always stick as close to official documentation and best practices as possible.
5. Do not write unit tests unless explicitly instructed to do so.
6. Do not run unit tests unless explicitly instructed to do so.
7. If you encounter any issues or have questions about the codebase, please ask for clarification before proceeding.
8. Follow the existing coding style and conventions used in the repository.
9. Ensure that any changes you make do not break existing functionality.
10. If you are unsure about any aspect of the code or the task at hand, please ask for clarification before proceeding.
11. When making changes, consider the impact on other parts of the system and ensure compatibility.
12. Always prioritize code readability and maintainability.
13. If you are making significant changes, consider discussing them with the team first to ensure alignment.
14. When working on a plan, ensure that you understand the overall goal and how your changes fit into that goal.
15. Make sure that when you create detailed plans, you create small, numbered tasks.
16. When creating detailed plans, make sure to include a checklist at the bottom of the file for tracking progress.
17. When doing a task that involves or interacts with other parts of the codebase, make sure to evaluate if there are other
    places in the codebase that need to be changed to reflect the changes being made.
18. When doing a task that involves or interacts with other parts of the codebase, make sure to use the naming conventions, existing environment variables, and existing variable names so that the two pieces connect to each other correctly.
19. Ensure that the plan created is not too complex.  MVP implementations should be as simple as possible while still meeting the requirements.
20. When coding in python, always use type hints.
21. Keep notes organized in the agent_notes/ folder.
22. Keep tests organized in the tests/ folder (and create subdirectories as needed).
23. Keep everything contained in its own folders, do not just write files in the root directory unless it is necessary (like plan files, git files, configurations, etc.).
24. Make sure that individual dockerized MCP servers are contained in their own folders, including the docker files, requirements.txt, and any other necessary files.
25. Do not add a -e line at the top of requirements.txt files.
26. When debugging a complicated issue, always assume that the problem is a simple one, go through simple solutions, and look for simple problems before jumping to complex problems and even more complex solutions.  We only want to make large, complex changes to our code if absolutely necessary. Always start simple.

### Documentation

- Update relevant docs in `docs/` folder when making architectural changes
- Add docstrings to all new tools with Args and Returns sections
- Update README.md if adding new features visible to end users
- Keep CLAUDE.md focused on high-level concepts only
