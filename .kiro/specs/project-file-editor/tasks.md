# Implementation Plan: Project File Editor

## Overview

Implement a three-panel project file editor at `/editor` within the existing NiceGUI application. The editor provides a file tree browser, a CodeMirror code editor with TJ syntax highlighting, and an inline agentic helper panel with LLM integration. Implementation follows a bottom-up approach: data models first, then services (EditorService, HelperService), then the UI page, and finally integration wiring.

## Tasks

- [x] 1. Define data models and core interfaces
  - [x] 1.1 Create editor data models in `src/tj_chat/editor_models.py`
    - Define `FileNode`, `FileContent`, `SaveResult`, `EditorContext`, `HelperResponse`, and `DiffSuggestion` Pydantic models
    - Include all fields, types, and defaults as specified in the design
    - Add the `file_type` classifier logic (`.tjp` → "tjp", `.tji` → "tji", else → "other")
    - Add the path display truncation utility function (max 60 chars, ellipsis prefix)
    - _Requirements: 2.2, 3.4, 6.1_

  - [x] 1.2 Write property test for file type classification
    - **Property 2: File type classification**
    - **Validates: Requirements 2.2**
    - Create `tests/property/test_editor_file_type_property.py`
    - For any file name, classifier returns "tjp" for `.tjp`, "tji" for `.tji`, "other" otherwise

  - [x] 1.3 Write property test for path display truncation
    - **Property 4: Path display truncation**
    - **Validates: Requirements 3.4**
    - Create `tests/property/test_editor_path_display_property.py`
    - For any path string: result ≤ 60 chars; if original > 60, result starts with ellipsis and ends with filename; if ≤ 60, returned unchanged

- [x] 2. Implement EditorService
  - [x] 2.1 Create `src/tj_chat/editor_service.py` with file tree building
    - Implement `EditorService.__init__` accepting `project_dir: Path` and `settings: ChatSettings`
    - Implement `build_file_tree()` that enumerates the project directory, excludes hidden entries, sorts directories-first then alphabetically, classifies file types, and validates paths through `PathSafetyModule`
    - Return `list[FileNode]` with recursive children for subdirectories
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 8.4_

  - [x] 2.2 Write property test for file tree structure invariant
    - **Property 1: File tree structure invariant**
    - **Validates: Requirements 2.1, 2.5**
    - Create `tests/property/test_editor_file_tree_property.py`
    - For any directory structure: directories listed before files at every level, both sorted alphabetically (case-insensitive), hidden entries excluded

  - [x] 2.3 Write property test for file tree path boundary
    - **Property 3: File tree path boundary**
    - **Validates: Requirements 2.6, 8.1, 8.4**
    - Add to `tests/property/test_editor_file_tree_property.py`
    - For any file node in the tree, its resolved path is within or equal to the project root

  - [x] 2.4 Implement file read operation in `EditorService`
    - Implement `async read_file(relative_path: str) -> FileContent`
    - Validate path through `PathSafetyModule` before reading
    - Return `FileContent` with success/error status
    - Handle read errors gracefully, returning error message in `FileContent`
    - _Requirements: 2.3, 2.8, 8.1_

  - [x] 2.5 Implement save workflow in `EditorService`
    - Implement `async save_file(relative_path: str, content: str) -> SaveResult`
    - Validate path through `PathSafetyModule`
    - Write content to a temporary file within the project directory
    - Invoke `tj3` compiler validation on the temp file
    - On success: create backup of original (`.bak`), persist new content, remove temp file
    - On failure: remove temp file, return compiler errors
    - Handle timeout (30s), missing compiler binary, and backup creation failure
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 4.9, 4.10_

  - [x] 2.6 Write property test for save workflow file integrity
    - **Property 6: Save workflow file integrity**
    - **Validates: Requirements 4.2, 4.3, 4.5**
    - Create `tests/property/test_editor_save_property.py`
    - With mocked compiler: on success, target has new content and backup exists; on failure, target unchanged and no backup created

  - [x] 2.7 Write property test for write path safety enforcement
    - **Property 7: Write path safety enforcement**
    - **Validates: Requirements 4.6, 8.2, 8.3**
    - Add to `tests/property/test_editor_save_property.py`
    - For any path outside project boundary, save rejects with security error and no file is modified

  - [x] 2.8 Write unit tests for EditorService
    - Create `tests/unit/test_editor_service.py`
    - Test file tree building with mocked filesystem
    - Test read_file with valid/invalid paths
    - Test save workflow success/failure/timeout scenarios
    - _Requirements: 2.1, 2.3, 2.8, 4.1–4.10, 8.1–8.4_

- [x] 3. Checkpoint - Ensure all EditorService tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement HelperService
  - [x] 4.1 Create `src/tj_chat/helper_service.py` with context assembly and LLM communication
    - Implement `HelperService.__init__` accepting `settings: ChatSettings` and `tj_docs: TJDocumentationService | None`
    - Implement `async send_message(user_message: str, context: EditorContext) -> HelperResponse`
    - Build context payload with file name, content, cursor line, surrounding lines (10 above/below), project file list, and TJ documentation search results
    - Use a dedicated system prompt instructing the LLM to respond with TJ syntax assistance and structured diff suggestions
    - Maintain conversation history for the session
    - Implement `reset_session()` to clear history
    - Handle ChatService timeout (120s) and unreachable errors
    - _Requirements: 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10, 7.1, 7.2, 7.3, 7.4, 9.1, 9.2_

  - [x] 4.2 Implement diff suggestion parsing in `HelperService`
    - Parse LLM response text for fenced code blocks annotated with file path and line range
    - Extract `DiffSuggestion` instances from annotated blocks
    - Return parsed suggestions in `HelperResponse.suggestions`
    - _Requirements: 6.1_

  - [x] 4.3 Implement whitespace input rejection
    - In the submission handler, reject empty or whitespace-only input without calling ChatService
    - _Requirements: 5.4_

  - [x] 4.4 Write property test for whitespace input rejection
    - **Property 8: Whitespace input rejection**
    - **Validates: Requirements 5.4**
    - Create `tests/property/test_editor_helper_property.py`
    - For any string of only whitespace/empty, submission is rejected without ChatService call

  - [x] 4.5 Write property test for helper context assembly
    - **Property 9: Helper context assembly**
    - **Validates: Requirements 5.5, 5.9, 7.1, 7.2**
    - Add to `tests/property/test_editor_helper_property.py`
    - For any message with a file loaded: context includes file name, content, cursor line, surrounding lines, and TJ doc results

  - [x] 4.6 Write property test for diff suggestion parsing
    - **Property 10: Diff suggestion parsing**
    - **Validates: Requirements 6.1**
    - Create `tests/property/test_editor_diff_property.py`
    - For any LLM response with annotated fenced code blocks, parser extracts one DiffSuggestion per block with correct fields

  - [x] 4.7 Write unit tests for HelperService
    - Create `tests/unit/test_helper_service.py`
    - Test context assembly, response parsing, session management, timeout handling
    - Mock ChatService and TJDocumentationService
    - _Requirements: 5.3–5.10, 7.1–7.4_

- [x] 5. Implement diff suggestion application logic
  - [x] 5.1 Create diff application utilities in `src/tj_chat/editor_models.py` or a dedicated module
    - Implement `apply_suggestion(content: str, suggestion: DiffSuggestion) -> tuple[str, bool]` that replaces lines at the referenced range if original content matches
    - Implement conflict detection: if editor content at line range doesn't match `original_content`, mark suggestion as "outdated" and return content unchanged
    - Ensure accepting/rejecting one suggestion doesn't affect others (independence)
    - _Requirements: 6.3, 6.4, 6.6, 6.7_

  - [x] 5.2 Write property test for diff suggestion application
    - **Property 11: Diff suggestion application**
    - **Validates: Requirements 6.3**
    - Add to `tests/property/test_editor_diff_property.py`
    - For any valid suggestion where line range matches original_content, accepting replaces exactly those lines, leaving others unchanged

  - [x] 5.3 Write property test for diff suggestion conflict detection
    - **Property 12: Diff suggestion conflict detection**
    - **Validates: Requirements 6.4**
    - Add to `tests/property/test_editor_diff_property.py`
    - For any suggestion where line range doesn't match original_content, suggestion marked "outdated" and content unchanged

  - [x] 5.4 Write property test for diff suggestion independence
    - **Property 13: Diff suggestion independence**
    - **Validates: Requirements 6.7**
    - Add to `tests/property/test_editor_diff_property.py`
    - For any set of multiple suggestions, accepting/rejecting one doesn't change status of others (non-overlapping ranges)

- [x] 6. Checkpoint - Ensure all service-layer tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Implement TJ syntax highlighting mode
  - [x] 7.1 Create TJ CodeMirror language mode configuration
    - Define the TJ keyword list, comment patterns (`#`, `//`, `/* */`), string patterns, number/date patterns, and operator patterns
    - Configure as a CodeMirror mode usable with NiceGUI's `ui.codemirror`
    - Place in `src/tj_chat/pages/editor.py` or a dedicated `src/tj_chat/tj_codemirror.py` module
    - _Requirements: 3.2_

  - [x] 7.2 Write property test for TJ tokenizer classification
    - **Property 5: TJ tokenizer classification**
    - **Validates: Requirements 3.2**
    - Create `tests/property/test_editor_tj_tokenizer_property.py`
    - For any known TJ keyword → classified as keyword; for `#`/`//` lines → comment; for quoted strings → string

- [x] 8. Implement EditorPageUI
  - [x] 8.1 Create `src/tj_chat/pages/editor.py` with three-panel layout
    - Implement `EditorPageUI` class with `__init__` accepting `EditorService`, `HelperService`, and `ChatSettings`
    - Implement `setup()` rendering the file tree (left), code editor (center), and helper panel (right)
    - Use responsive layout: side-by-side at ≥1024px, stacked vertically below
    - Display placeholder message in editor when no file is selected
    - _Requirements: 1.3, 3.9_

  - [x] 8.2 Implement file tree UI component
    - Render `FileNode` tree as collapsible NiceGUI tree component
    - Show distinct visual indicators for `.tjp`, `.tji`, and other files
    - Directories collapsed by default
    - On file click: check for unsaved changes, prompt if dirty, then load file
    - Handle file read errors with notification
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7, 2.8_

  - [x] 8.3 Implement code editor component with save workflow
    - Use `ui.codemirror` with TJ language mode, monospace font, line numbers
    - Display file path in header (truncated per design)
    - Show unsaved changes indicator (asterisk)
    - Bind Ctrl+S and save button to save workflow
    - Disable save button and show loading indicator during save
    - Display compiler errors in collapsible error panel on failure
    - Preserve cursor position and scroll state after save
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 4.1, 4.7_

  - [x] 8.4 Implement helper panel UI component
    - Render collapsible side panel with toggle button
    - Provide text input (max 2000 chars) for user messages
    - Display scrollable conversation area with message history
    - Show loading indicator during LLM requests
    - Display error messages inline with retry button for unreachable service
    - Render `DiffSuggestion` components with Accept/Reject buttons
    - Handle accept: apply suggestion to editor, mark as accepted, set dirty flag
    - Handle reject: disable buttons, show rejected state
    - Handle outdated: show indication that content has changed
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.6, 5.7, 5.8, 5.10, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8_

- [x] 9. Wire editor page into application routing
  - [x] 9.1 Register `/editor` route and update navigation header in `src/tj_chat/app.py`
    - Add `@ui.page("/editor")` route that instantiates `EditorService` and `HelperService`, then renders `EditorPageUI`
    - Add "Editor" link to `_nav_header()` between "Admin" and "Chat"
    - Highlight "Editor" link as active when current path is `/editor`
    - Reuse existing `ChatSettings`, `TJDocumentationService`, and project path configuration
    - _Requirements: 1.1, 1.2, 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 9.2 Write unit tests for editor page routing and navigation
    - Create `tests/unit/test_editor_page.py`
    - Test that `/editor` route is registered
    - Test navigation header includes "Editor" link
    - Test EditorPageUI instantiation with mocked services
    - _Requirements: 1.1, 1.2_

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (13 properties total)
- Unit tests validate specific examples and edge cases
- All file operations use `PathSafetyModule` for boundary enforcement
- The project uses `uv run pytest --tb=short -q` for test execution
- Hypothesis is already in dev dependencies for property-based testing

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 3, "tasks": ["2.6", "2.7", "2.8", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "7.1"] },
    { "id": 5, "tasks": ["4.4", "4.5", "4.6", "4.7", "5.1", "7.2"] },
    { "id": 6, "tasks": ["5.2", "5.3", "5.4"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["8.2", "8.3", "8.4"] },
    { "id": 9, "tasks": ["9.1"] },
    { "id": 10, "tasks": ["9.2"] }
  ]
}
```
