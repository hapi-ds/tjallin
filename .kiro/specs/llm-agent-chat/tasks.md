# Implementation Plan: LLM Agent Chat

## Overview

Replace the Ruby-based tj-web service with a unified NiceGUI Python application that consolidates report viewing, admin panel, and LLM agent chat into a single service. The implementation follows a bottom-up approach: core utilities and data models first, then service layers (including TJ documentation integration), then UI pages, and finally Docker integration and documentation.

## Tasks

- [x] 1. Set up project structure and core modules
  - [x] 1.1 Create `src/tj_chat` package with settings and data models
    - Create `src/tj_chat/__init__.py`
    - Create `src/tj_chat/settings.py` with `ChatSettings` pydantic-settings class (env prefix `TJ_CHAT_`, fields: `lm_studio_url`, `model_name`, `token_limit`, `connection_timeout`, `response_timeout`, `default_author`, `project_path`, `project_file`, `reports_path`, `tj_docs_path`, `web_port`)
    - Create `src/tj_chat/models.py` with all Pydantic data models from the design: `Message`, `ToolCallMessage`, `FunctionCall`, `ToolCall`, `ToolResult`, `AgentResponse`, `ToolAction`, `ConfirmationRequest`, `ConnectionResult`, `CompilerResult`, `SystemStatus`, `ReportFile`, `BookingStatus`, `TaskEntry`, `BookingRequest`, `JournalEntryRequest`, `ReportType`, `ReportRequest`, `TaskInfo`, `ResourceInfo`, `TaskMatch`, `ResourceMatch`, `ProjectSummary`, `PathSecurityError`, `DocSection`
    - Add `nicegui`, `openai`, `httpx` to project dependencies via `uv add`
    - _Requirements: 1.1, 1.6, 12.1, 13.1_

  - [x] 1.2 Implement path safety module
    - Create `src/tj_chat/path_safety.py` with `validate_project_path()` and `is_within_project()` functions
    - Resolve paths to canonical absolute form (handling `..`, `.`, symlinks)
    - Raise `PathSecurityError` for paths outside project boundary
    - _Requirements: 7.3, 7.4, 7.5_

  - [x] 1.3 Write property tests for path safety
    - **Property 1: Path security rejects out-of-bounds paths**
    - **Validates: Requirements 7.3, 7.4, 7.5**
    - Create `tests/property/test_tj_chat_path_safety_property.py`

- [x] 2. Implement project reader and generators
  - [x] 2.1 Implement project reader
    - Create `src/tj_chat/project_reader.py` with `ProjectReader` class
    - Implement `get_project_summary()` to parse project name, dates, file tree, resources, top-level tasks from `.tjp` and `.tji` files
    - Implement `list_tasks()` and `list_resources()` to extract structured info
    - Implement `find_task()` and `find_resource()` with similarity search (max 5 results, ordered by score)
    - Implement `get_file_tree()` to list project directory contents
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.5, 5.6_

  - [x] 2.2 Write property test for task similarity search
    - **Property 10: Task similarity search returns bounded ordered results**
    - **Validates: Requirements 4.5, 5.6**
    - Create `tests/property/test_tj_chat_search_property.py`

  - [x] 2.3 Implement timesheet generator
    - Create `src/tj_chat/generators.py` with `TimesheetGenerator` class
    - Implement `generate()` to produce valid `timesheet` blocks from `BookingRequest`
    - Implement `merge_into_existing()` to merge new entries into existing timesheet files (replace matching task path, preserve others)
    - Generate filenames matching pattern `YYYY-Www-<resource_id>.tji`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.8_

  - [x] 2.4 Write property tests for timesheet generation
    - **Property 5: Timesheet generation produces valid structure**
    - **Property 6: Timesheet file naming convention**
    - **Property 7: Timesheet merge preserves unrelated entries**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.8**
    - Create `tests/property/test_tj_chat_timesheet_property.py`

  - [x] 2.5 Implement journal entry generator
    - Add `JournalEntryGenerator` class to `src/tj_chat/generators.py`
    - Implement `generate()` to produce valid `journalentry` statements with date (YYYY-MM-DD), author, headline (≤120 chars), and optional summary
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 2.6 Write property test for journal entry generation
    - **Property 8: Journal entry generation produces valid syntax**
    - **Validates: Requirements 5.1**
    - Create `tests/property/test_tj_chat_journal_property.py`

  - [x] 2.7 Implement report generator
    - Add `ReportGenerator` class to `src/tj_chat/generators.py`
    - Implement `generate()` to produce valid TaskJuggler report definitions with type, ID, title, columns, formats, sort order, hide expressions, time scales
    - _Requirements: 9.1, 9.2, 9.4_

  - [x] 2.8 Write property test for report generation
    - **Property 9: Report generation produces valid structure**
    - **Validates: Requirements 9.1**
    - Create `tests/property/test_tj_chat_report_property.py`

  - [x] 2.9 Implement task generator
    - Add `TaskGenerator` class to `src/tj_chat/generators.py`
    - Implement `generate()` to produce valid TaskJuggler task definitions with ID, name, effort, and allocation
    - _Requirements: 3.2_

  - [x] 2.10 Write property test for task generation
    - **Property 18: Task generation includes required attributes**
    - **Validates: Requirements 3.2**
    - Create `tests/property/test_tj_chat_task_gen_property.py`

- [x] 3. Implement TJ Documentation Service
  - [x] 3.1 Prepare TaskJuggler reference documentation
    - Create `docs/tj-reference/` directory in the repository
    - Download/extract TaskJuggler reference documentation from the tj3 gem (`gem contents taskjuggler` or from taskjuggler.org manual pages)
    - Organize docs into structured text/markdown files by construct: `task.md`, `resource.md`, `account.md`, `report.md`, `timesheet.md`, `journalentry.md`, `macro.md`, `project.md`, `shift.md`, `vacation.md`, `statussheet.md`, `columns.md` (standard column identifiers)
    - Ensure coverage of: project, task, resource, account, shift, vacation, timesheet, statussheet, journalentry, report types (taskreport, resourcereport, accountreport, textreport, statusreport), macros, includes, and all standard column identifiers
    - _Requirements: 13.1, 13.7_

  - [x] 3.2 Implement TJDocumentationService class
    - Create `src/tj_chat/tj_docs.py` with `TJDocumentationService` class
    - Implement `__init__(docs_path: Path)` that loads all documentation files from the configured path; if path is missing or unreadable, log a warning and set degraded mode
    - Implement `search(query: str) -> list[DocSection]` performing case-insensitive matching against section titles and content, returning results ordered by relevance score
    - Implement `get_syntax_reference() -> str` returning a condensed syntax reference covering key constructs (task, resource, account, report, timesheet, journalentry, macros) for inclusion in the system prompt; returns empty string if docs unavailable
    - Implement `is_available` property indicating whether docs were successfully loaded
    - _Requirements: 13.1, 13.4, 13.5, 13.8_

  - [x] 3.3 Write property test for TJ docs search
    - **Property 19: TJ docs search returns relevant sections matching query terms**
    - **Validates: Requirements 13.5**
    - Create `tests/property/test_tj_chat_tj_docs_property.py`

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement conversation manager
  - [x] 5.1 Implement conversation manager
    - Create `src/tj_chat/conversation.py` with `ConversationManager` class
    - Implement `add_message()` preserving insertion order
    - Implement `get_messages()` returning ordered history with system prompt
    - Implement `truncate_to_limit()` removing oldest messages first while preserving system prompt and minimum 4 recent exchanges
    - Implement `estimate_tokens()` for token counting (chars/4 approximation)
    - Implement `clear()` to reset session
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 5.2 Write property tests for conversation manager
    - **Property 11: Conversation history preserves message order**
    - **Property 12: Conversation truncation respects token limit and preserves recent context**
    - **Validates: Requirements 6.1, 6.2, 6.3**
    - Create `tests/property/test_tj_chat_conversation_property.py`

  - [x] 5.3 Implement system prompt builder
    - Add `build_system_prompt()` to `ChatService` or as standalone function
    - Include project file tree, tool names, include file descriptions, resource IDs, top-level tasks
    - Include condensed TJ syntax reference from `TJDocumentationService.get_syntax_reference()` when documentation is available
    - If docs exceed token budget, include condensed reference only and rely on `search_tj_docs` tool for full details
    - _Requirements: 6.4, 13.3, 13.4_

  - [x] 5.4 Write property test for system prompt content
    - **Property 13: System prompt contains project structure, tool names, and TJ syntax reference**
    - **Validates: Requirements 6.4, 13.3, 13.4**
    - Add test to `tests/property/test_tj_chat_conversation_property.py`

- [x] 6. Implement tool executor and safety layer
  - [x] 6.1 Implement tool executor
    - Create `src/tj_chat/tool_executor.py` with `ToolExecutor` class
    - Implement `execute()` dispatching tool calls to appropriate handlers (read_file, list_files, list_tasks, list_resources, find_task, find_resource, write_file, update_task, add_task, update_resource, write_timesheet, write_journal, write_report, compile_project, search_tj_docs)
    - Wire `search_tj_docs` tool to `TJDocumentationService.search()` — accepts a `query: str` parameter and returns matching `DocSection` results
    - Implement `validate_path()` using path safety module
    - Implement `create_backup()` creating `.bak` copy before writes
    - Implement `validate_with_compiler()` running `tj3` against project after proposed changes
    - For write operations: backup → write → validate → rollback on failure
    - _Requirements: 3.4, 3.5, 3.6, 7.1, 7.3, 7.4, 7.5, 13.5_

  - [x] 6.2 Write property tests for backup and compiler safety
    - **Property 2: Backup creation before file writes**
    - **Property 3: Failed compilation preserves original file**
    - **Property 4: Declined write operations preserve file state**
    - **Validates: Requirements 3.5, 3.6, 7.2**
    - Create `tests/property/test_tj_chat_backup_property.py` and `tests/property/test_tj_chat_compiler_safety_property.py`

  - [x] 6.3 Write property test for write confirmation summary
    - **Property 17: Write confirmation summary contains required information**
    - **Validates: Requirements 7.1**
    - Create `tests/property/test_tj_chat_confirmation_property.py`

- [x] 7. Implement chat service
  - [x] 7.1 Implement chat service core
    - Create `src/tj_chat/chat_service.py` with `ChatService` class
    - Implement `connect()` to verify LM Studio connectivity (models endpoint, 10s timeout)
    - Implement `send_message()` orchestrating: build messages → call LM Studio → handle tool calls → return response
    - Implement tool call loop: parse tool_calls from LLM response, execute via ToolExecutor, feed results back to LLM
    - Use `openai` client library with custom base_url pointing to LM Studio
    - Handle model selection: use configured model or first from models list
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 11.2_

  - [x] 7.2 Implement overdue detection and proactive guidance
    - Add overdue task detection based on project `now` date
    - Implement session-start summary: overdue tasks, upcoming milestones (14 days), missing timesheets
    - Implement follow-up suggestions after bookings/updates
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 7.3 Write property test for overdue detection
    - **Property 14: Overdue detection uses configured project date**
    - **Validates: Requirements 8.4, 8.5**
    - Create `tests/property/test_tj_chat_overdue_property.py`

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement NiceGUI web application pages
  - [x] 9.1 Create NiceGUI app entry point and navigation
    - Create `src/tj_chat/app.py` with `create_app()` function
    - Set up page routing: `/` (home), `/reports`, `/admin`, `/chat`
    - Implement shared navigation layout with links to all pages
    - Configure static file serving for reports volume at `/report-files`
    - Add `[project.scripts]` entry `tj-web = "tj_chat.app:main"` in pyproject.toml
    - _Requirements: 12.2, 12.6_

  - [x] 9.2 Implement home page
    - Create `src/tj_chat/pages/__init__.py`
    - Create `src/tj_chat/pages/home.py` with project status summary
    - Display report count, timesheet count, project file status, link to chat
    - _Requirements: 12.7_

  - [x] 9.3 Implement reports page
    - Create `src/tj_chat/pages/reports.py` with `ReportsPageUI` class
    - List available HTML reports from reports volume
    - Embed or link to report files for viewing
    - Handle empty reports directory with helpful message
    - _Requirements: 12.3_

  - [x] 9.4 Implement admin page
    - Create `src/tj_chat/pages/admin.py` with `AdminPageUI` class
    - Add rebuild button that triggers `tj3` compilation
    - Display compilation result (success with report count, or error details)
    - Show system status: project file existence, report count, timesheet count, LM Studio connection
    - _Requirements: 12.4, 12.5_

  - [x] 9.5 Implement chat page UI
    - Create `src/tj_chat/pages/chat.py` with `ChatPageUI` class
    - Implement message input field and scrollable message history
    - Display loading spinner during agent processing
    - Show tool action summaries as system messages (tool name + one-line summary)
    - Implement Accept/Decline buttons for write confirmations inline in conversation
    - Visually distinguish user messages, agent responses, system messages, and tool actions
    - Display notice when TJ documentation is unavailable (degraded mode)
    - _Requirements: 11.1, 11.3, 11.4, 11.9, 11.10, 13.8_

  - [x] 9.6 Implement slash commands and input validation
    - Handle `/reset` command to clear conversation and start new session
    - Handle `/help` command to display available commands and capabilities
    - Reject unknown slash commands with error and `/help` suggestion
    - Reject empty/whitespace-only input without sending to agent
    - _Requirements: 11.5, 11.6, 11.7, 11.8_

  - [x] 9.7 Write property tests for input validation
    - **Property 15: Whitespace-only input is rejected without agent invocation**
    - **Property 16: Unknown slash commands produce help suggestion**
    - **Validates: Requirements 11.7, 11.8**
    - Create `tests/property/test_tj_chat_input_property.py`

  - [x] 9.8 Implement graceful degradation
    - Show connection error banner on chat page when LM Studio is unreachable (with endpoint URL and retry button)
    - Ensure reports and admin pages remain fully functional when LM Studio is offline
    - _Requirements: 12.8, 1.2_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Docker integration and service replacement
  - [x] 11.1 Update tj-web Dockerfile for Python/NiceGUI
    - Replace Ruby-based Dockerfile with Python 3.11-slim base
    - Install tj3 (Ruby + taskjuggler gem) for compilation
    - Install Python dependencies via uv
    - Copy `src/` application code
    - Bundle TaskJuggler reference documentation: `COPY docs/tj-reference/ /app/tj-docs/`
    - Set entrypoint to `uv run tj-web`
    - Expose port 8080
    - _Requirements: 12.1, 12.6, 13.2_

  - [x] 11.2 Update docker-compose.yml for new tj-web service
    - Remove second port mapping (9090 admin port no longer needed — unified on 8080)
    - Add `TJ_CHAT_LM_STUDIO_URL` environment variable (pointing to host LM Studio)
    - Add `TJ_CHAT_TJ_DOCS_PATH` environment variable (default `/app/tj-docs`)
    - Ensure volume mounts remain: project path (read/write), report-data (read)
    - Update healthcheck to use Python-based endpoint
    - _Requirements: 12.1, 12.6, 13.1_

  - [x] 11.3 Update `.env.example` with new chat-related variables
    - Add `TJ_CHAT_LM_STUDIO_URL`, `TJ_CHAT_MODEL_NAME`, `TJ_CHAT_TOKEN_LIMIT`, `TJ_CHAT_DEFAULT_AUTHOR`, `TJ_CHAT_CONNECTION_TIMEOUT`, `TJ_CHAT_RESPONSE_TIMEOUT`, `TJ_CHAT_TJ_DOCS_PATH`
    - _Requirements: 1.4, 1.6, 13.1_

- [x] 12. Documentation updates
  - [x] 12.1 Update README.md
    - Add section describing LLM agent chat capability, purpose, and URL (`/chat`)
    - Add LM Studio prerequisite with minimum compatible version in Quick Start or linked setup section
    - Mention bundled TaskJuggler documentation for enhanced syntax accuracy
    - _Requirements: 10.1, 10.5, 13.1_

  - [x] 12.2 Update docs/user-guide.md
    - Add instructions for installing and configuring LM Studio
    - Document accessing the web interface (reports, admin, chat)
    - Document `/reset` and `/help` commands
    - Add Configuration Reference table entries for all `TJ_CHAT_*` environment variables (name, required/optional, default, description) including `TJ_CHAT_TJ_DOCS_PATH`
    - Add example conversations for: plan review, task/resource updates, booking creation, journal entry creation, report creation
    - Document the `search_tj_docs` tool capability and how the agent uses bundled documentation
    - _Requirements: 10.2, 10.3, 10.4, 13.1_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The project uses `uv` for dependency management and `src/` layout per project conventions
- NiceGUI replaces both the WEBrick file server (port 8080) and Ruby admin server (port 9090) with a single app on port 8080
- LM Studio communicates via OpenAI-compatible API — the `openai` Python client is used with a custom `base_url`
- TaskJuggler reference documentation is bundled in the Docker image at `/app/tj-docs` for offline availability; the service degrades gracefully if docs are missing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1"] },
    { "id": 2, "tasks": ["1.3", "2.2", "2.3", "2.5", "2.7", "2.9", "3.2"] },
    { "id": 3, "tasks": ["2.4", "2.6", "2.8", "2.10", "3.3", "5.1"] },
    { "id": 4, "tasks": ["5.2", "5.3"] },
    { "id": 5, "tasks": ["5.4", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 7, "tasks": ["7.2"] },
    { "id": 8, "tasks": ["7.3", "9.1"] },
    { "id": 9, "tasks": ["9.2", "9.3", "9.4"] },
    { "id": 10, "tasks": ["9.5", "9.6"] },
    { "id": 11, "tasks": ["9.7", "9.8"] },
    { "id": 12, "tasks": ["11.1", "11.2", "11.3"] },
    { "id": 13, "tasks": ["12.1", "12.2"] }
  ]
}
```
